"""
FSN C1: interactive helper for the physical tests. Watches meal_logs (read-only) for new scale captures and asks for
the ground truth of each one.

  --scale     (H1)  prints the NutriX weight, asks object_id, ref_g, trial          -> v2/H1_scale.csv
  --servings  (H2)  prints food, source, weight, kcal + macros, asks true_food, ref_g, is_packaged and (packaged only)
                    the label's kcal/protein/carbs/fat per 100 g                     -> v2/H2_servings.csv
                    (+ capture image path, YOLO top-1 + confidence, VLM output from MS1's capture record)

At any prompt: "skip" logs the capture as skipped, "undo" removes the last saved entry and asks for it again.
Ctrl+C stops cleanly; a half-answered capture is not saved. Re-run the same command to resume: captures already in the
CSV are never asked twice, captures that arrived while it was stopped are asked next. The first start remembers the
newest meal_logs id in <csv>.state.json; only captures after it are asked.

DB access: the app's own shared.db session in a READ ONLY transaction; no credentials are printed.
MS1's capture record (dataset/live_captures/log/<meal_log_id>.json) is written by MS1 >= this commit; restart MS1 first.

  PYTHONPATH=. python scripts/fsn_capture_logger.py --scale
  PYTHONPATH=. python scripts/fsn_capture_logger.py --servings
  PYTHONPATH=. python scripts/fsn_capture_logger.py --servings --dry-run 2      # last 2 existing rows, to a temp CSV
"""
import argparse
import csv
import datetime as dt
import json
import os
import tempfile
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "paper-upgrade" / "results" / "fsn" / "v2"
CAPTURE_LOG_DIR = ROOT / "dataset" / "live_captures" / "log"
SCALE_MEAL_TYPE = "Scale Capture"

H1_COLS = ["object_id", "ref_g", "trial", "nutrix_g", "meal_log_id", "timestamp", "status"]
H2_COLS = ["meal_log_id", "timestamp", "status", "food_name", "source", "weight_g", "kcal", "protein_g", "carbs_g", "fat_g",
           "true_food", "ref_g", "is_packaged", "label_kcal_100g", "label_protein_100g", "label_carbs_100g", "label_fat_100g",
           "image_path", "yolo_top1", "yolo_conf", "conf_threshold", "vlm_food", "vlm_conf", "vlm_flagged", "vlm_flag_reason",
           "vlm_kcal_100g", "vlm_protein_100g", "vlm_carbs_100g", "vlm_fat_100g", "macro_source", "meal_log_source"]
SOURCE_SHORT = {"esp32_yolo": "yolo", "esp32_qwen_vlm": "qwen", "llm-timeout": "timeout", "no_nutrition_data": "no_nutrition_data"}


class Skip(Exception):
    pass


class Undo(Exception):
    pass


# ── CSV ledger (append-only, fsync per row; undo rewrites without the last row) ─────────────────────
class Ledger:
    def __init__(self, path, cols):
        self.path, self.cols = Path(path), cols
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() or self.path.stat().st_size == 0:
            with open(self.path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=cols).writeheader()

    def rows(self):
        with open(self.path, newline="") as f:
            return list(csv.DictReader(f))

    def ids(self):
        return {int(r["meal_log_id"]) for r in self.rows() if r.get("meal_log_id")}

    def append(self, row):
        with open(self.path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=self.cols, extrasaction="ignore").writerow(row)
            f.flush()
            os.fsync(f.fileno())

    def undo(self):
        rows = self.rows()
        if not rows:
            return None
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.cols)
            w.writeheader()
            w.writerows(rows[:-1])
        os.replace(tmp, self.path)
        return rows[-1]


# ── DB (read-only) ─────────────────────────────────────────────────────────────────────────────────
class MealLogSource:
    def __init__(self, user_id=None):
        self.user_id = user_id

    def _query(self, fn):
        from sqlalchemy import text
        from shared.db import SessionLocal
        db = SessionLocal()
        try:
            try:
                db.execute(text("SET TRANSACTION READ ONLY"))
            except Exception:
                db.rollback()            # not Postgres
            return fn(db)
        finally:
            db.rollback()
            db.close()

    def _base(self, db):
        from shared.models import MealLog
        q = db.query(MealLog).filter(MealLog.meal_type == SCALE_MEAL_TYPE)
        return q.filter(MealLog.user_id == self.user_id) if self.user_id else q

    @staticmethod
    def _plain(m):
        return dict(id=m.id, user_id=m.user_id, log_date=str(m.log_date), food_name=m.food_name, calories=m.calories,
                    protein=m.protein, carbs=m.carbs, fat=m.fat, weight_g=m.weight_g, source=m.source)

    def max_id(self):
        from shared.models import MealLog
        return self._query(lambda db: max([m.id for m in self._base(db).order_by(MealLog.id.desc()).limit(1)] or [0]))

    def after(self, after_id):
        from shared.models import MealLog
        return self._query(lambda db: [self._plain(m) for m in self._base(db).filter(MealLog.id > after_id).order_by(MealLog.id)])

    def by_id(self, mid):
        from shared.models import MealLog
        return self._query(lambda db: next((self._plain(m) for m in self._base(db).filter(MealLog.id == mid)), None))

    def last(self, n):
        from shared.models import MealLog
        return self._query(lambda db: [self._plain(m) for m in self._base(db).order_by(MealLog.id.desc()).limit(n)][::-1])


def capture_record(meal_log_id, log_dir=CAPTURE_LOG_DIR):
    p = Path(log_dir) / f"{meal_log_id}.json"
    return json.loads(p.read_text()) if p.exists() else None


# ── prompts ────────────────────────────────────────────────────────────────────────────────────────
def ask(inp, prompt, kind="str"):
    while True:
        a = inp(prompt).strip()
        if a.lower() == "skip":
            raise Skip
        if a.lower() == "undo":
            raise Undo
        if kind == "float":
            try:
                v = float(a)
                if v >= 0:
                    return v
            except ValueError:
                pass
            print("   enter a number >= 0 (or skip / undo)")
        elif kind == "int":
            if a.isdigit():
                return int(a)
            print("   enter a whole number (or skip / undo)")
        elif kind == "yn":
            if a.lower() in ("y", "n", "yes", "no"):
                return "y" if a.lower().startswith("y") else "n"
            print("   enter y or n (or skip / undo)")
        elif a:
            return a
        else:
            print("   cannot be empty (or skip / undo)")


def _ts(rec):
    return (rec or {}).get("logged_at_utc") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def show_scale(m, rec):
    print(f"\n── meal_log #{m['id']}  NutriX weight: {m['weight_g']} g   ({m['food_name']}, {m['source']})")


def ask_scale(inp, m, rec):
    return dict(object_id=ask(inp, "   object_id: "), ref_g=ask(inp, "   ref_g (reference weight, g): ", "float"),
                trial=ask(inp, "   trial number: ", "int"))


def scale_row(m, rec, answers, status):
    return {**{k: "" for k in H1_COLS}, **(answers or {}),
            "nutrix_g": m["weight_g"], "meal_log_id": m["id"], "timestamp": _ts(rec), "status": status}


def show_servings(m, rec):
    src = SOURCE_SHORT.get(m["source"], m["source"])
    print(f"\n── meal_log #{m['id']}  {m['food_name']}  source={src}  weight={m['weight_g']} g")
    print(f"   kcal {m['calories']}  protein {m['protein']} g  carbs {m['carbs']} g  fat {m['fat']} g")
    if rec:
        v = rec.get("vlm") or {}
        print(f"   YOLO top-1: {rec.get('yolo_top1')} ({rec.get('yolo_conf')})  status {rec.get('yolo_status')}  "
              f"VLM: {v.get('food_name', '-')}{' [flagged]' if v.get('flagged') else ''}  macros from {rec.get('macro_source')}")
    else:
        print("   (no MS1 capture record for this row: YOLO/VLM fields will be blank; is MS1 running the current code?)")
    if src == "no_nutrition_data" or not m["calories"]:
        print("   NOTE: logged with no nutrition data (0 kcal is missing data, not a measurement)")


def ask_servings(inp, m, rec):
    a = dict(true_food=ask(inp, "   true_food: "), ref_g=ask(inp, "   ref_g (reference weight, g): ", "float"),
             is_packaged=ask(inp, "   is_packaged (y/n): ", "yn"))
    if a["is_packaged"] == "y":
        for k, label in (("label_kcal_100g", "kcal"), ("label_protein_100g", "protein g"),
                         ("label_carbs_100g", "carbs g"), ("label_fat_100g", "fat g")):
            a[k] = ask(inp, f"   label {label} per 100 g: ", "float")
    return a


def servings_row(m, rec, answers, status):
    rec = rec or {}
    v = rec.get("vlm") or {}
    p = v.get("per_100g") or {}
    return {**{k: "" for k in H2_COLS}, **(answers or {}), **dict(
        meal_log_id=m["id"], timestamp=_ts(rec), status=status,
        food_name=m["food_name"], source=SOURCE_SHORT.get(m["source"], m["source"]), weight_g=m["weight_g"],
        kcal=m["calories"], protein_g=m["protein"], carbs_g=m["carbs"], fat_g=m["fat"],
        image_path=rec.get("image_path") or "", yolo_top1=rec.get("yolo_top1") or "",
        yolo_conf=rec.get("yolo_conf", ""), conf_threshold=rec.get("conf_threshold", ""),
        vlm_food=v.get("food_name", ""), vlm_conf=v.get("confidence", ""), vlm_flagged=v.get("flagged", ""),
        vlm_flag_reason=v.get("flag_reason") or "", vlm_kcal_100g=p.get("calories", ""), vlm_protein_100g=p.get("protein_g", ""),
        vlm_carbs_100g=p.get("carbs_g", ""), vlm_fat_100g=p.get("fat_g", ""),
        macro_source=rec.get("macro_source", ""), meal_log_source=m["source"])}


MODES = {"scale": (H1_COLS, show_scale, ask_scale, scale_row, "H1_scale.csv"),
         "servings": (H2_COLS, show_servings, ask_servings, servings_row, "H2_servings.csv")}


# ── main loop ──────────────────────────────────────────────────────────────────────────────────────
def run(mode, ledger, src, inp=input, poll_s=1.0, initial=None, stop_when_empty=False, start_after=None, log_dir=CAPTURE_LOG_DIR):
    """initial: rows to process first (dry run). start_after: only rows with a larger id are watched."""
    cols, show, asker, mkrow, _ = MODES[mode]
    done = ledger.ids()
    queue = deque(r for r in (initial or []) if r["id"] not in done)
    watermark = max([start_after or 0] + [r["id"] for r in queue])
    if not initial:
        queue.extend(r for r in src.after(start_after or 0) if r["id"] not in done)
        watermark = max([watermark] + [r["id"] for r in queue])
    waiting_msg = False
    while True:
        if not queue:
            if stop_when_empty:
                return
            new = [r for r in src.after(watermark) if r["id"] not in ledger.ids()]
            if not new:
                if not waiting_msg:
                    print("\nwaiting for the next scale capture ... (Ctrl+C to stop)")
                    waiting_msg = True
                time.sleep(poll_s)
                continue
            queue.extend(new)
            watermark = max(r["id"] for r in new)
        waiting_msg = False
        m = queue[0]
        rec = capture_record(m["id"], log_dir)
        show(m, rec)
        try:
            ans = asker(inp, m, rec)
        except Skip:
            ledger.append(mkrow(m, rec, None, "skipped"))
            queue.popleft()
            print(f"   skipped #{m['id']}")
            continue
        except Undo:
            last = ledger.undo()
            if last is None:
                print("   nothing to undo")
            else:
                mid = int(last["meal_log_id"])
                print(f"   removed the last entry (meal_log #{mid}); asking for it again")
                again = next((r for r in queue if r["id"] == mid), None) or src.by_id(mid)
                if again is not None and again is not m:
                    queue.appendleft(again)
            continue
        ledger.append(mkrow(m, rec, ans, "ok"))
        queue.popleft()
        print(f"   saved #{m['id']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--scale", action="store_true", help="H1 weighing test")
    g.add_argument("--servings", action="store_true", help="H2 servings test")
    ap.add_argument("--user-id", type=int, default=None, help="only this user's captures (default: any user)")
    ap.add_argument("--out", default=None, help="CSV path (default: results/fsn/v2/H1_scale.csv or H2_servings.csv)")
    ap.add_argument("--dry-run", type=int, default=0, metavar="N", help="process the last N existing captures into a temp CSV and exit")
    ap.add_argument("--poll", type=float, default=1.0)
    a = ap.parse_args(argv)
    mode = "scale" if a.scale else "servings"
    src = MealLogSource(a.user_id)
    if a.dry_run:
        out = Path(a.out or Path(tempfile.gettempdir()) / f"fsn_dryrun_{MODES[mode][4]}")
        print(f"DRY RUN: last {a.dry_run} existing captures -> {out}")
        out.unlink(missing_ok=True)
        ledger = Ledger(out, MODES[mode][0])
        try:
            run(mode, ledger, src, initial=src.last(a.dry_run), stop_when_empty=True)
        except (KeyboardInterrupt, EOFError):
            print("\nstopped")
        print(f"dry run wrote {len(ledger.rows())} rows to {out}")
        return
    out = Path(a.out or OUT / MODES[mode][4])
    ledger = Ledger(out, MODES[mode][0])
    state = out.with_suffix(out.suffix + ".state.json")
    if state.exists():
        start_after = json.loads(state.read_text())["start_after_id"]
    else:
        start_after = src.max_id()
        state.write_text(json.dumps({"start_after_id": start_after, "created": dt.datetime.now().isoformat(timespec="seconds")}))
    print(f"{mode}: writing {out}  ({len(ledger.rows())} entries so far; watching captures after meal_log #{start_after})")
    print('type "skip" or "undo" at any prompt; Ctrl+C to stop (re-run the same command to resume)')
    try:
        run(mode, ledger, src, poll_s=a.poll, start_after=start_after)
    except (KeyboardInterrupt, EOFError):
        print(f"\nstopped. {len(ledger.rows())} entries in {out}. Re-run the same command to resume.")


if __name__ == "__main__":
    main()
