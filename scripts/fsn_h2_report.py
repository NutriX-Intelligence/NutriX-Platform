"""
FSN C3: H2 servings report from v2/H2_servings.csv (rows with status=ok).

Identification (95 % bootstrap CIs; match rule + synonym groups = scripts/eval_fallback_ablation.is_match):
  * YOLO-only, recomputed from the stored YOLO top-1 and confidence at threshold 0.5 (below it = abstain = wrong);
    also YOLO raw top-1 (never abstains). Rows without an MS1 capture record (no YOLO fields) are left out of these.
  * the logged pipeline result (meal_logs food_name).
Weight: NutriX weight - ref_g.
Energy / macros per serving: reference = ref_g / 100 x reference per-100 g value, where the reference is
  the pack label (packaged items), INDB (Indian dishes, v1 S4 crosswalk or exact INDB name), or USDA FDC SR Legacy
  (raw foods in v2/fdc_reference_per100g.csv). Foods with none of these can be given one in v2/H2_reference_map.csv
  (columns: true_food, ref_source, ref_code, kcal, protein, carbs, fat; per 100 g) - unmatched foods are listed.
  Error = logged value - reference. no_nutrition_data / 0 kcal rows are excluded from energy error and listed.
Energy error decomposition (per serving, kcal; the parts add up to the total error exactly):
  composition    = ref_g/100 x DB(true food)        - reference            (right food, right weight, DB value)
  identification = ref_g/100 x DB(predicted food)   - ref_g/100 x DB(true food)
  weight         = NutriX_g/100 x DB(predicted food) - ref_g/100 x DB(predicted food)
  macro source   = logged kcal - NutriX_g/100 x DB(predicted food)   (logged value came from Qwen, not the DB, ...)
  DB(.) = per-100 g kcal from the current shared.food_lookup (read-only). Rows where a DB value is missing are left out.

  PYTHONPATH=. python scripts/fsn_h2_report.py [--csv path] [--out-dir dir]
"""
import argparse
import csv
import json
import re
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_fallback_ablation as ab  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "paper-upgrade" / "results" / "fsn" / "v2"
INDB = ROOT / "dataset" / "ms3_datasets" / "INDB.xlsx"
THRESHOLD = 0.5
NUTS = ("kcal", "protein", "carbs", "fat")
LOGGED = {"kcal": "kcal", "protein": "protein_g", "carbs": "carbs_g", "fat": "fat_g"}
LABEL = {"kcal": "label_kcal_100g", "protein": "label_protein_100g", "carbs": "label_carbs_100g", "fat": "label_fat_100g"}


def f(x):
    return None if x in ("", None, "None") else float(x)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


# ── references ─────────────────────────────────────────────────────────────────────────────────────
class References:
    """true_food -> (source, code, {kcal, protein, carbs, fat} per 100 g) or None."""

    def __init__(self, out_dir=OUT, indb_path=INDB):
        import pandas as pd
        from fsn_s4_macro import CROSSWALK
        self.indb = pd.read_excel(indb_path).set_index("food_code")
        self.cw = {k.replace(" ", ""): code for k, (_, code, _) in CROSSWALK.items()}
        self.idx = {}
        for code, name in zip(self.indb.index, self.indb.food_name):
            for k in {norm(re.sub(r"\(.*?\)", "", name))} | {norm(p) for p in re.findall(r"\((.*?)\)", name)}:
                if k:
                    self.idx.setdefault(k, code)
        self.fdc, self.manual = {}, {}
        p = Path(out_dir) / "fdc_reference_per100g.csv"
        if p.exists():
            for r in csv.DictReader(open(p, newline="")):
                self.fdc[norm(r["food"])] = (r["ref_source"], r["ref_code"], {k: float(r[f"ref_{k}"]) for k in NUTS})
        p = Path(out_dir) / "H2_reference_map.csv"
        if p.exists():
            for r in csv.DictReader(open(p, newline="")):
                self.manual[norm(r["true_food"])] = (r["ref_source"], r["ref_code"], {k: float(r[k]) for k in NUTS})

    def _indb(self, code):
        row = self.indb.loc[code]
        return "INDB", code, {"kcal": float(row["energy_kcal"]), "protein": float(row["protein_g"]),
                              "carbs": float(row["carb_g"]), "fat": float(row["fat_g"])}

    def get(self, true_food):
        k = norm(true_food)
        if k in self.manual:
            return self.manual[k]
        if k.replace(" ", "") in self.cw:
            return self._indb(self.cw[k.replace(" ", "")])
        if k in self.fdc:
            return self.fdc[k]
        if k in self.idx:
            return self._indb(self.idx[k])
        return None


def db_kcal_lookup():
    """name -> per-100 g kcal from the app's lookup (read-only session), or None."""
    from sqlalchemy import text
    from shared.db import SessionLocal
    from shared.food_lookup import lookup_food, per_100g
    db = SessionLocal()
    db.execute(text("SET TRANSACTION READ ONLY"))
    memo = {}

    def get(name):
        if name not in memo:
            food = lookup_food(db, name) if name else None
            memo[name] = per_100g(food)["calories"] if food else None
        return memo[name]
    return get


# ── stats ─────────────────────────────────────────────────────────────────────────────────────────
def acc(values):
    if not values:
        return None
    m, lo, hi = ab.bootstrap_ci(values)
    return {"n": len(values), "acc": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)]}


def err_stats(est, ref):
    pairs = [(e, r) for e, r in zip(est, ref) if e is not None and r is not None]
    if len(pairs) < 2:
        return {"n": len(pairs)}
    d = [e - r for e, r in pairs]
    ape = [abs(e - r) / r * 100 for e, r in pairs if r >= 1.0]
    bias, sd = st.mean(d), st.stdev(d)
    return {"n": len(d), "bias": round(bias, 2), "MAE": round(st.mean(map(abs, d)), 2),
            "MAPE_pct": round(st.mean(ape), 1) if ape else None, "median_APE_pct": round(st.median(ape), 1) if ape else None,
            "loa": [round(bias - 1.96 * sd, 2), round(bias + 1.96 * sd, 2)]}


def analyse(rows, refs, db_kcal):
    ok = [r for r in rows if r.get("status", "ok") == "ok"]
    nonutr = [r for r in ok if r["source"] == "no_nutrition_data" or not f(r["kcal"])]
    with_yolo = [r for r in ok if r.get("yolo_top1") and f(r.get("yolo_conf")) is not None]
    ident = {
        "yolo_only_t0.5": acc([float(f(r["yolo_conf"]) >= THRESHOLD and ab.is_match(r["yolo_top1"], r["true_food"])) for r in with_yolo]),
        "yolo_raw_top1": acc([float(ab.is_match(r["yolo_top1"], r["true_food"])) for r in with_yolo]),
        "pipeline_logged": acc([float(ab.is_match(r["food_name"], r["true_food"])) for r in ok]),
        "pipeline_logged_on_rows_with_yolo": acc([float(ab.is_match(r["food_name"], r["true_food"])) for r in with_yolo]),
    }
    if with_yolo:
        a = [float(ab.is_match(r["food_name"], r["true_food"])) for r in with_yolo]
        b = [float(f(r["yolo_conf"]) >= THRESHOLD and ab.is_match(r["yolo_top1"], r["true_food"])) for r in with_yolo]
        d, lo, hi = ab.paired_diff_ci(a, b)
        ident["pipeline_minus_yolo_only"] = {"diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)]}
    weight = err_stats([f(r["weight_g"]) for r in ok], [f(r["ref_g"]) for r in ok])

    per, unmatched = [], []
    for r in ok:
        if r in nonutr:
            continue                 # excluded from energy error; listed separately
        if r["is_packaged"] == "y" and f(r.get("label_kcal_100g")) is not None:
            src, code, ref100 = "label", "pack label", {k: f(r[LABEL[k]]) for k in NUTS}
        else:
            got = refs.get(r["true_food"])
            if got is None:
                unmatched.append(r["true_food"])
                continue
            src, code, ref100 = got
        refg = f(r["ref_g"])
        row = {"meal_log_id": r["meal_log_id"], "true_food": r["true_food"], "logged_food": r["food_name"], "ref_source": src,
               "ref_code": code, "id_correct": ab.is_match(r["food_name"], r["true_food"]), "no_nutrition_data": r in nonutr}
        for k in NUTS:
            row[f"ref_{k}"] = round(refg / 100 * ref100[k], 2)
            row[f"logged_{k}"] = f(r[LOGGED[k]])
        dt, dp = db_kcal(r["true_food"]), db_kcal(r["food_name"])
        if dt is not None and dp is not None and not row["no_nutrition_data"]:
            a_ = refg / 100 * dt
            b_ = refg / 100 * dp
            c_ = f(r["weight_g"]) / 100 * dp
            row.update(composition=round(a_ - row["ref_kcal"], 2), identification=round(b_ - a_, 2),
                       weight=round(c_ - b_, 2), macro_source=round(row["logged_kcal"] - c_, 2),
                       total=round(row["logged_kcal"] - row["ref_kcal"], 2))
        per.append(row)
    scored = [p for p in per if not p["no_nutrition_data"]]
    groups = {"all": scored, "packaged (label)": [p for p in scored if p["ref_source"] == "label"],
              "Indian (INDB)": [p for p in scored if p["ref_source"] == "INDB"],
              "raw / other (USDA)": [p for p in scored if p["ref_source"].startswith("USDA")],
              "manual reference": [p for p in scored if p["ref_source"] not in ("label", "INDB") and not p["ref_source"].startswith("USDA")]}
    energy = {g: {k: err_stats([p[f"logged_{k}"] for p in ps], [p[f"ref_{k}"] for p in ps]) for k in NUTS} for g, ps in groups.items()}
    dec_rows = [p for p in scored if "total" in p]
    parts = ("composition", "identification", "weight", "macro_source")
    decomp = {"n": len(dec_rows)}
    if dec_rows:
        tot_abs = sum(abs(p[c]) for p in dec_rows for c in parts)
        for c in parts:
            decomp[c] = {"mean_kcal": round(st.mean(p[c] for p in dec_rows), 2), "mean_abs_kcal": round(st.mean(abs(p[c]) for p in dec_rows), 2),
                         "share_of_abs_pct": round(100 * sum(abs(p[c]) for p in dec_rows) / tot_abs, 1) if tot_abs else None}
        decomp["total"] = {"mean_kcal": round(st.mean(p["total"] for p in dec_rows), 2), "mean_abs_kcal": round(st.mean(abs(p["total"]) for p in dec_rows), 2)}
    return dict(n_rows=len(rows), n_ok=len(ok), n_skipped=len(rows) - len(ok), n_with_yolo_record=len(with_yolo),
                n_packaged=sum(r["is_packaged"] == "y" for r in ok), identification=ident, weight_error_g=weight,
                energy_macro_error_per_serving=energy, decomposition=decomp,
                no_nutrition_data=[{"meal_log_id": r["meal_log_id"], "food_name": r["food_name"], "source": r["source"], "kcal": r["kcal"]} for r in nonutr],
                unmatched_reference=sorted(set(unmatched)), threshold=THRESHOLD), per


def render(s):
    L = ["# H2: servings test (generated by scripts/fsn_h2_report.py)", "",
         f"Rows: {s['n_rows']} ({s['n_ok']} ok, {s['n_skipped']} skipped); packaged {s['n_packaged']}; "
         f"with an MS1 capture record (YOLO fields): {s['n_with_yolo_record']}.", "",
         "## Identification (95 % bootstrap CI)", "", "| system | n | accuracy | 95 % CI |", "|---|---|---|---|"]
    for k, v in s["identification"].items():
        if v and "acc" in v:
            L.append(f"| {k} | {v['n']} | {v['acc']} | {v['ci95']} |")
    d = s["identification"].get("pipeline_minus_yolo_only")
    if d:
        L += ["", f"Paired difference pipeline - YOLO-only (t = {s['threshold']}): {d['diff']} (95 % CI {d['ci95']})."]
    w = s["weight_error_g"]
    L += ["", "## Weight error (NutriX - reference, g)", "", f"{json.dumps(w)}", "",
          "## Energy and macro error per serving (logged - reference)", "",
          "| subset | nutrient | n | bias | MAE | MAPE % | median APE % | 95 % LoA |", "|---|---|---|---|---|---|---|---|"]
    for g, ks in s["energy_macro_error_per_serving"].items():
        for k, m in ks.items():
            if m.get("n", 0) >= 2:
                L.append(f"| {g} | {k} | {m['n']} | {m['bias']} | {m['MAE']} | {m['MAPE_pct']} | {m['median_APE_pct']} | {m['loa']} |")
    dc = s["decomposition"]
    L += ["", f"## Energy error decomposition (kcal per serving, n = {dc['n']})", "",
          "| component | mean (signed) | mean absolute | share of total absolute % |", "|---|---|---|---|"]
    for c in ("composition", "identification", "weight", "macro_source"):
        if c in dc:
            L.append(f"| {c} | {dc[c]['mean_kcal']} | {dc[c]['mean_abs_kcal']} | {dc[c]['share_of_abs_pct']} |")
    if "total" in dc:
        L.append(f"| total | {dc['total']['mean_kcal']} | {dc['total']['mean_abs_kcal']} | |")
    L += ["", f"## no_nutrition_data / 0 kcal rows: {len(s['no_nutrition_data'])}", ""]
    L += [f"- #{r['meal_log_id']} {r['food_name']} ({r['source']}, {r['kcal']} kcal)" for r in s["no_nutrition_data"]]
    L += ["", f"Foods without a reference (add them to H2_reference_map.csv): {', '.join(s['unmatched_reference']) or 'none'}", ""]
    return "\n".join(L)


def main(argv=None, refs=None, db_kcal=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(OUT / "H2_servings.csv"))
    ap.add_argument("--out-dir", default=str(OUT))
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(a.csv, newline="")))
    s, per = analyse(rows, refs or References(), db_kcal or db_kcal_lookup())
    (out / "H2_summary.json").write_text(json.dumps(s, indent=2))
    if per:
        cols = sorted({k for p in per for k in p}, key=lambda k: list(per[0]).index(k) if k in per[0] else 99)
        with open(out / "H2_per_serving.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(per)
    md = render(s)
    (out / "H2_summary.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
