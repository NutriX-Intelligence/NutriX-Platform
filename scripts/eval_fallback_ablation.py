"""
Labelled ablation of the YOLO -> Qwen3-VL fallback on the held-out test split.

Systems compared on the SAME images (single-item images only, like a scale plate):
  yolo_raw      YOLO top-1, no abstention (what the paper's detector would say)
  yolo_abstain  YOLO top-1 if conf >= threshold and class not suppressed, else "unknown" (pre-LLM behaviour:
                low confidence was logged as Unknown)
  vlm_only      Qwen3-VL on every image, no YOLO hint
  hybrid        production path: YOLO if confident, else Qwen (with the YOLO hint unless suppressed)

Qwen is reached over HTTP (MS2 must be running: it already holds ~4.2 GB of the 6 GB GPU, so loading a second copy
here would OOM). YOLO runs locally.

  PYTHONPATH=. python scripts/eval_fallback_ablation.py --per-class 3 --seed 0
Results are cached per image (jsonl) so an interrupted run resumes.
"""
import argparse
import csv
import json
import os
import random
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dataset" / "custom_training_data"
INDIAN_CSV = ROOT / "docs" / "Raj Docs" / "rajDocs5" / "indian_dish_subset_results.csv"
OUT_DIR = ROOT / "docs" / "paper-upgrade" / "results"

# Visually/semantically identical concepts; applied identically to every system.
SYNONYM_GROUPS = [
    {"brinjal", "eggplant", "green brinjal", "aubergine"},
    {"capsicum", "bell pepper", "green pepper", "sweet pepper"},
    {"chili pepper", "hot pepper", "chilli", "chili", "green chilli"},
    {"jack fruit", "jackfruit"},
    {"wallnut", "walnut"},
    {"pea", "peas", "green peas"},
    {"mandarin", "tangerine", "clementine"},
    {"rice", "white rice", "whiterice", "rice chamal"},
    {"yoghurt", "curd", "yogurt"},
]


# ── pure helpers (unit-tested in tests/test_eval_fallback_ablation.py) ──────────────────────────
def clean_class_name(name: str) -> str:
    """'ash gourd -kubhindo-' -> 'ash gourd'; lowercase, underscores to spaces."""
    name = re.sub(r"\s*-[^-]*-\s*$", "", name or "")
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip().lower()


def _singular(s: str) -> str:
    return s[:-1] if len(s) > 3 and s.endswith("s") and not s.endswith("ss") else s


def is_match(pred: str, gt: str) -> bool:
    """Exact after normalisation, space-less equality, or same synonym group. Word-subset matches are NOT accepted
    ('potato' != 'sweet potato'), so the metric cannot be inflated by vague answers."""
    p, g = _singular(clean_class_name(pred)), _singular(clean_class_name(gt))
    if not p or p in ("unknown", "none", "error"):
        return False
    if p == g or p.replace(" ", "") == g.replace(" ", ""):
        return True
    for grp in SYNONYM_GROUPS:
        grp = {_singular(x) for x in grp}
        if p in grp and g in grp:
            return True
    return False


def bootstrap_ci(values: Sequence[float], n_boot: int = 2000, seed: int = 0, alpha: float = 0.05) -> Tuple[float, float, float]:
    """(mean, lo, hi) percentile bootstrap over per-image values."""
    vals = list(values)
    if not vals:
        return (float("nan"),) * 3
    rng = random.Random(seed)
    n = len(vals)
    means = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return sum(vals) / n, means[int(alpha / 2 * n_boot)], means[int((1 - alpha / 2) * n_boot) - 1]


def paired_diff_ci(a: Sequence[float], b: Sequence[float], n_boot: int = 2000, seed: int = 0) -> Tuple[float, float, float]:
    """Bootstrap CI of mean(a - b) over the same images."""
    return bootstrap_ci([x - y for x, y in zip(a, b)], n_boot=n_boot, seed=seed)


def single_class_of(label_file: Path) -> Optional[int]:
    """Class id if the label file contains exactly one distinct class, else None."""
    try:
        ids = {int(l.split()[0]) for l in label_file.read_text().splitlines() if l.strip()}
    except (OSError, ValueError, IndexError):
        return None
    return next(iter(ids)) if len(ids) == 1 else None


# ── data ────────────────────────────────────────────────────────────────────────────────────────
def load_class_names() -> Dict[int, str]:
    import yaml
    names = yaml.safe_load((DATA / "data.yaml").read_text())["names"]
    return dict(names) if isinstance(names, dict) else dict(enumerate(names))


def load_indian_classes() -> Set[str]:
    if not INDIAN_CSV.exists():
        return set()
    with open(INDIAN_CSV, newline="", encoding="utf-8") as f:
        return {row["class_name"].strip().lower() for row in csv.DictReader(f)}


def sample_images(split: str, per_class: int, seed: int, names: Dict[int, str]) -> List[Tuple[Path, str]]:
    by_class: Dict[int, List[Path]] = defaultdict(list)
    base = Path(split) if Path(split).is_absolute() else DATA / split   # absolute path = custom folder (images/ + labels/)
    for lbl in sorted((base / "labels").glob("*.txt")):
        cid = single_class_of(lbl)
        if cid is None:
            continue
        for ext in (".jpg", ".jpeg", ".png"):
            img = base / "images" / (lbl.stem + ext)
            if img.exists():
                by_class[cid].append(img)
                break
    rng = random.Random(seed)
    out = []
    for cid in sorted(by_class):
        imgs = by_class[cid]
        rng.shuffle(imgs)
        out += [(p, names[cid]) for p in imgs[:per_class]]
    return out


# ── inference ───────────────────────────────────────────────────────────────────────────────────
def yolo_top1(model, path: Path) -> Tuple[str, float, float]:
    t0 = time.perf_counter()
    res = model(str(path), verbose=False)[0]
    ms = (time.perf_counter() - t0) * 1000
    if len(res.boxes) == 0:
        return "none", 0.0, ms
    confs = [float(b.conf[0]) for b in res.boxes]
    i = max(range(len(confs)), key=confs.__getitem__)
    return res.names[int(res.boxes[i].cls[0])], confs[i], ms


def vlm_call(client, url: str, path: Path, hint: Optional[str]) -> Tuple[str, bool, float]:
    t0 = time.perf_counter()
    with open(path, "rb") as f:
        r = client.post(url, files={"image": (path.name, f, "image/jpeg")}, data={"yolo_hint": hint} if hint else {})
    ms = (time.perf_counter() - t0) * 1000
    if r.status_code != 200:
        return "error", True, ms
    j = r.json()
    return j.get("food_name", "unknown"), bool(j.get("flagged")), ms


def run(args):
    import httpx
    from ultralytics import YOLO

    names = load_class_names()
    indian = load_indian_classes()
    samples = sample_images(args.split, args.per_class, args.seed, names)
    if args.limit:
        samples = samples[: args.limit]
    suppressed = {c.strip().lower() for c in os.getenv("YOLO_SUPPRESSED_CLASSES", "lassi,kulfi").split(",") if c.strip()}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = OUT_DIR / f"ablation_cache_{Path(args.split).name}_pc{args.per_class}_s{args.seed}.jsonl"
    cache = {}
    if cache_path.exists():
        cache = {json.loads(l)["image"]: json.loads(l) for l in cache_path.read_text().splitlines() if l.strip()}

    model = YOLO(args.weights)
    url = args.ms2.rstrip("/") + "/api/v1/llm/vision-infer"
    print(f"{len(samples)} images, {len(cache)} cached, threshold={args.threshold}")
    with httpx.Client(timeout=120) as client, open(cache_path, "a") as out:
        for i, (path, gt) in enumerate(samples, 1):
            if path.name in cache:
                continue
            y_cls, y_conf, y_ms = yolo_top1(model, path)
            is_supp = y_cls.lower() in suppressed
            fallback = y_conf < args.threshold or is_supp
            v_cls, v_flag, v_ms = vlm_call(client, url, path, None)          # VLM-only baseline (no hint)
            h_cls, h_flag, h_ms = (v_cls, v_flag, v_ms)
            if fallback and not args.no_hint_pass:                              # production path: hinted call
                h_cls, h_flag, h_ms = vlm_call(client, url, path, None if is_supp or y_cls == "none" else y_cls)
            rec = dict(image=path.name, gt=gt, yolo=y_cls, yolo_conf=round(y_conf, 4), yolo_ms=round(y_ms, 1),
                       suppressed=is_supp, fallback=fallback, vlm=v_cls, vlm_flagged=v_flag, vlm_ms=round(v_ms, 1),
                       hybrid_vlm=h_cls, hybrid_vlm_ms=round(h_ms, 1))
            cache[path.name] = rec
            out.write(json.dumps(rec) + "\n")
            out.flush()
            if i % 25 == 0:
                print(f"  {i}/{len(samples)}")
    summarize(list(cache.values()), indian, args)


def summarize(recs: List[dict], indian: Set[str], args):
    match = is_match

    def correct(system: str, r: dict) -> float:
        gt = r["gt"]
        if system == "yolo_raw":
            return float(match(r["yolo"], gt))
        if system == "yolo_abstain":
            return float((not r["fallback"]) and match(r["yolo"], gt))
        if system == "vlm_only":
            return float(match(r["vlm"], gt))
        return float(match(r["yolo"], gt)) if not r["fallback"] else float(match(r["hybrid_vlm"], gt))

    systems = ["yolo_raw", "yolo_abstain", "vlm_only", "hybrid"]
    subsets = {"all": recs,
               "indian_dishes": [r for r in recs if clean_class_name(r["gt"]) in indian],
               "other_foods": [r for r in recs if clean_class_name(r["gt"]) not in indian]}
    summary = {"n_images": len(recs), "threshold": args.threshold, "match": "exact+synonyms",
               "fallback_rate": sum(r["fallback"] for r in recs) / max(1, len(recs)), "accuracy": {}, "latency_ms": {}}
    for sname, sub in subsets.items():
        summary["accuracy"][sname] = {"n": len(sub)}
        for s in systems:
            m, lo, hi = bootstrap_ci([correct(s, r) for r in sub])
            summary["accuracy"][sname][s] = {"acc": round(m, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        d, lo, hi = paired_diff_ci([correct("hybrid", r) for r in sub], [correct("yolo_abstain", r) for r in sub])
        summary["accuracy"][sname]["hybrid_minus_yolo_abstain"] = {"diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)]}
    fb = [r for r in recs if r["fallback"]]
    acc_fb = lambda f: (sum(f(r) for r in fb) / len(fb)) if fb else float("nan")
    summary["on_fallback_images"] = {"n": len(fb),
                                     "yolo_raw_acc": round(acc_fb(lambda r: correct("yolo_raw", r)), 4),
                                     "hybrid_acc": round(acc_fb(lambda r: correct("hybrid", r)), 4)}
    acc_acc = [r for r in recs if not r["fallback"]]
    summary["yolo_accepted_precision"] = round(sum(correct("yolo_raw", r) for r in acc_acc) / max(1, len(acc_acc)), 4)

    def pct(xs, q):
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(q * len(xs)))], 1) if xs else None
    summary["latency_ms"] = {"yolo_p50": pct([r["yolo_ms"] for r in recs], .5), "yolo_p95": pct([r["yolo_ms"] for r in recs], .95),
                             "vlm_p50": pct([r["hybrid_vlm_ms"] for r in fb], .5), "vlm_p95": pct([r["hybrid_vlm_ms"] for r in fb], .95)}
    out = OUT_DIR / f"ablation_summary_{Path(args.split).name}_pc{args.per_class}_s{args.seed}_t{args.threshold}.json"
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\nsaved {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", help="test | valid | absolute folder with images/ and labels/")
    ap.add_argument("--per-class", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0, help="cap images (smoke test)")
    ap.add_argument("--threshold", type=float, default=float(os.getenv("YOLO_CONF_THRESHOLD", "0.5")))
    ap.add_argument("--weights", default=str(ROOT / "backend/services/ingestion/best.pt"))
    ap.add_argument("--ms2", default="http://localhost:8003")
    ap.add_argument("--no-hint-pass", action="store_true", help="hybrid reuses the unhinted VLM call (fewer calls)")
    run(ap.parse_args())
