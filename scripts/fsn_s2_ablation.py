"""
S2/S3/S5 (FSN runbook): labelled fallback ablation with threshold-independent caching, DB/alias-resolved hybrid score,
leak-free subset, and a resolution-tier log for every VLM name.

Differences from scripts/eval_fallback_ablation.py (left untouched):
  * the cache holds the YOLO top-1 + conf, the UNHINTED VLM answer and the HINTED VLM answer for every image, so the
    fallback decision is made at summary time -> any threshold can be scored from one cache (no frozen decisions);
  * VLM names are also resolved through the knowledge layer (exact / alias / partial / miss) and scored on the canonical
    food name ("*_resolved" columns), with the raw-name columns kept;
  * subsets: all / indian / other / leak-free (test images with no train near-duplicate, from S3_dedup.csv);
  * writes S5_lookup_tiers.csv.

MS2 must be running (it holds the Qwen). YOLO runs locally.
  PYTHONPATH=. python scripts/fsn_s2_ablation.py --per-class 3 --seed 0 --thresholds 0.3 0.5 0.75

v2 (FSN follow-up): output goes to results/fsn/v2 by default (v1 files are never written), the tier comes from
shared.food_lookup.lookup_food_with_tier (no mirrored copy that can drift), leak-free sets work for any split
(valid or test vs train), and a paired bootstrap CI of hybrid_resolved - yolo_raw is added.
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_fallback_ablation as ab  # noqa: E402  (helpers: matcher, bootstrap, sampler)

ROOT = ab.ROOT
OUT = ROOT / "docs" / "paper-upgrade" / "results" / "fsn" / "v2"
V1 = ROOT / "docs" / "paper-upgrade" / "results" / "fsn"
SYSTEMS = ["yolo_raw", "yolo_abstain", "vlm_only", "vlm_only_resolved", "hybrid", "hybrid_resolved"]


# ── inference (cached, threshold independent) ──────────────────────────────────────────────────
def vlm_call(client, url, path, hint):
    t0 = time.perf_counter()
    with open(path, "rb") as f:
        r = client.post(url, files={"image": (path.name, f, "image/jpeg")}, data={"yolo_hint": hint} if hint else {})
    ms = (time.perf_counter() - t0) * 1000
    if r.status_code != 200:
        return dict(name="error", flagged=True, reason=f"http {r.status_code}", ms=ms)
    j = r.json()
    return dict(name=j.get("food_name", "unknown"), flagged=bool(j.get("flagged")), reason=j.get("flag_reason"), ms=ms)


def collect(args, samples):
    import httpx
    from ultralytics import YOLO

    suppressed = {c.strip().lower() for c in os.getenv("YOLO_SUPPRESSED_CLASSES", "lassi,kulfi").split(",") if c.strip()}
    OUT.mkdir(parents=True, exist_ok=True)
    split_tag = Path(args.split).name
    cache_path = OUT / f"S2_cache_{split_tag}_pc{args.per_class}_s{args.seed}.jsonl"
    cache = {}
    if cache_path.exists():
        cache = {json.loads(l)["image"]: json.loads(l) for l in cache_path.read_text().splitlines() if l.strip()}
    model = YOLO(args.weights)
    url = args.ms2.rstrip("/") + "/api/v1/llm/vision-infer"
    print(f"{len(samples)} images, {len(cache)} cached", flush=True)
    with httpx.Client(timeout=180) as client, open(cache_path, "a") as out:
        for i, (path, gt) in enumerate(samples, 1):
            if path.name in cache:
                continue
            y_cls, y_conf, y_ms = ab.yolo_top1(model, path)
            is_supp = y_cls.lower() in suppressed
            u = vlm_call(client, url, path, None)
            hint = None if is_supp or y_cls == "none" else y_cls
            h = vlm_call(client, url, path, hint)
            rec = dict(image=path.name, gt=gt, yolo=y_cls, yolo_conf=round(y_conf, 4), yolo_ms=round(y_ms, 1),
                       suppressed=is_supp, hint=hint, vlm=u["name"], vlm_flagged=u["flagged"], vlm_flag_reason=u["reason"],
                       vlm_ms=round(u["ms"], 1), hybrid_vlm=h["name"], hybrid_flagged=h["flagged"],
                       hybrid_flag_reason=h["reason"], hybrid_vlm_ms=round(h["ms"], 1))
            cache[path.name] = rec
            out.write(json.dumps(rec) + "\n")
            out.flush()
            if i % 25 == 0:
                print(f"  {i}/{len(samples)}", flush=True)
    return [cache[p.name] for p, _ in samples if p.name in cache]


# ── knowledge-layer resolution ─────────────────────────────────────────────────────────────────
def lookup_tier(db, name):
    """(tier, Food, consistent) from the app's own lookup (shared.food_lookup.lookup_food_with_tier)."""
    from shared.food_lookup import lookup_food, lookup_food_with_tier, normalize_name
    clean = normalize_name(name)
    if not clean or clean in ("unknown", "error"):
        return "miss", None, True
    tier, food = lookup_food_with_tier(db, name)
    ref = lookup_food(db, name)
    consistent = (ref.id if ref else None) == (food.id if food else None)
    return tier, food, consistent


def resolve_all(recs):
    from shared.db import SessionLocal
    db = SessionLocal()
    memo, rows = {}, []
    for r in recs:
        for field in ("vlm", "hybrid_vlm"):
            name = r[field]
            if name not in memo:
                memo[name] = lookup_tier(db, name)
            tier, food, consistent = memo[name]
            r[f"{field}_tier"] = tier
            r[f"{field}_canon"] = food.name if food else None
            rows.append(dict(source_call=field, image=r["image"], gt=r["gt"], vlm_name=name, tier=tier,
                             canonical_food=food.name if food else "", canonical_food_id=food.id if food else "",
                             brand=(food.brand or "") if food else "", consistent_with_lookup_food=consistent,
                             raw_name_matches_gt=ab.is_match(name, r["gt"]),
                             canonical_matches_gt=bool(food) and ab.is_match(food.name, r["gt"]),
                             manual_verdict=""))
    db.close()
    return rows


# ── scoring ────────────────────────────────────────────────────────────────────────────────────
def fallback_of(r, thr):
    return r["yolo_conf"] < thr or r["suppressed"]


def correct(system, r, thr):
    m, gt, fb = ab.is_match, r["gt"], fallback_of(r, thr)
    canon = lambda f: (r.get(f"{f}_canon") or "")
    if system == "yolo_raw":
        return float(m(r["yolo"], gt))
    if system == "yolo_abstain":
        return float((not fb) and m(r["yolo"], gt))
    if system == "vlm_only":
        return float(m(r["vlm"], gt))
    if system == "vlm_only_resolved":
        return float(m(r["vlm"], gt) or m(canon("vlm"), gt))
    if system == "hybrid":
        return float(m(r["yolo"], gt)) if not fb else float(m(r["hybrid_vlm"], gt))
    return float(m(r["yolo"], gt)) if not fb else float(m(r["hybrid_vlm"], gt) or m(canon("hybrid_vlm"), gt))


def summarize(recs, thr, indian, leak_free_names):
    subsets = {"all": recs,
               "indian_dishes": [r for r in recs if ab.clean_class_name(r["gt"]) in indian],
               "other_foods": [r for r in recs if ab.clean_class_name(r["gt"]) not in indian]}
    if leak_free_names is not None:
        lf = [r for r in recs if r["image"] in leak_free_names]
        subsets["leak_free"] = lf
        subsets["leak_free_indian"] = [r for r in lf if ab.clean_class_name(r["gt"]) in indian]
        subsets["leak_free_other"] = [r for r in lf if ab.clean_class_name(r["gt"]) not in indian]
    s = {"threshold": thr, "n_images": len(recs), "match": "exact+plural+space-less+synonym groups", "accuracy": {}}
    for name, sub in subsets.items():
        fb = [r for r in sub if fallback_of(r, thr)]
        entry = {"n": len(sub), "fallback_rate": round(len(fb) / max(1, len(sub)), 4), "n_fallback": len(fb)}
        for sy in SYSTEMS:
            mean, lo, hi = ab.bootstrap_ci([correct(sy, r, thr) for r in sub])
            entry[sy] = {"acc": round(mean, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        if sub:
            d, lo, hi = ab.paired_diff_ci([correct("hybrid_resolved", r, thr) for r in sub],
                                          [correct("yolo_abstain", r, thr) for r in sub])
            entry["hybrid_resolved_minus_yolo_abstain"] = {"diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)]}
            d, lo, hi = ab.paired_diff_ci([correct("hybrid_resolved", r, thr) for r in sub],
                                          [correct("yolo_raw", r, thr) for r in sub])
            entry["hybrid_resolved_minus_yolo_raw"] = {"diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        if fb:
            entry["on_fallback_images"] = {sy: round(sum(correct(sy, r, thr) for r in fb) / len(fb), 4)
                                           for sy in ("yolo_raw", "vlm_only", "vlm_only_resolved", "hybrid", "hybrid_resolved")}
            lo_hi = {sy: [round(x, 4) for x in ab.bootstrap_ci([correct(sy, r, thr) for r in fb])[1:]]
                     for sy in ("yolo_raw", "hybrid", "hybrid_resolved")}
            entry["on_fallback_images_ci95"] = lo_hi
        acc = [r for r in sub if not fallback_of(r, thr)]
        entry["yolo_accepted_precision"] = round(sum(correct("yolo_raw", r, thr) for r in acc) / max(1, len(acc)), 4)
        s["accuracy"][name] = entry
    return s


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 1) if xs else None


def main(args):
    names = ab.load_class_names()
    indian = ab.load_indian_classes()
    samples = ab.sample_images(args.split, args.per_class, args.seed, names)
    if args.limit:
        samples = samples[: args.limit]
    recs = collect(args, samples)

    covered = {ab.clean_class_name(r["gt"]) for r in recs}
    all_classes = sorted(ab.clean_class_name(n) for n in names.values())
    missing = [c for c in all_classes if c not in covered]
    tier_rows = resolve_all(recs)
    tag = f"{Path(args.split).name}_pc{args.per_class}_s{args.seed}"

    leak_file = V1 / "S3_dedup.csv"          # S3 output (v1, read only)
    leak_free = None
    if leak_file.exists():
        with open(leak_file, newline="") as f:
            leak_free = {r["query_image"] for r in csv.DictReader(f)
                         if r["query_split"] == Path(args.split).name and r["ref_split"] == "train" and r["near_dup"] == "0"}

    OUT.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for thr in args.thresholds:
        summaries[thr] = summarize(recs, thr, indian, leak_free)
        (OUT / f"S2_summary_{tag}_t{thr}.json").write_text(json.dumps(summaries[thr], indent=2))

    # per-image table at every threshold
    with open(OUT / f"S2_per_image_{tag}.csv", "w", newline="") as f:
        cols = ["image", "gt", "indian", "yolo", "yolo_conf", "suppressed", "vlm", "vlm_tier", "vlm_canon",
                "hybrid_vlm", "hybrid_vlm_tier", "hybrid_vlm_canon", "leak_free"] + \
               [f"{sy}_t{t}" for t in args.thresholds for sy in SYSTEMS] + [f"fallback_t{t}" for t in args.thresholds]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            row = {c: r.get(c) for c in cols if c in r}
            row["indian"] = ab.clean_class_name(r["gt"]) in indian
            row["leak_free"] = (r["image"] in leak_free) if leak_free is not None else ""
            for t in args.thresholds:
                row[f"fallback_t{t}"] = fallback_of(r, t)
                for sy in SYSTEMS:
                    row[f"{sy}_t{t}"] = int(correct(sy, r, t))
            w.writerow(row)

    with open(OUT / f"S5_lookup_tiers_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(tier_rows[0]))
        w.writeheader()
        w.writerows(tier_rows)

    lat = {"yolo_p50": pct([r["yolo_ms"] for r in recs], .5), "yolo_p95": pct([r["yolo_ms"] for r in recs], .95),
           "vlm_unhinted_p50_excl_first": pct([r["vlm_ms"] for r in recs[1:]], .5),
           "vlm_hinted_p50_excl_first": pct([r["hybrid_vlm_ms"] for r in recs[1:]], .5),
           "vlm_hinted_p95_excl_first": pct([r["hybrid_vlm_ms"] for r in recs[1:]], .95)}
    meta = {"n_images": len(recs), "classes_total": len(names), "classes_covered": len(covered),
            "classes_without_single_item_test_image": missing, "n_missing": len(missing),
            "indian_classes_in_csv": len(indian), "n_leak_free": len(leak_free & {r["image"] for r in recs}) if leak_free is not None else None,
            "latency_ms": lat, "ms2_errors": sum(r["vlm"] == "error" for r in recs) + sum(r["hybrid_vlm"] == "error" for r in recs),
            "split": Path(args.split).name, "per_class": args.per_class, "seed": args.seed,
            "food_lookup_partial_enabled": __import__("shared.food_lookup", fromlist=["x"]).partial_enabled()}
    (OUT / f"S2_meta_{tag}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    for t, s in summaries.items():
        a = s["accuracy"]["all"]
        print(f"t={t}: fallback={a['fallback_rate']} " + " ".join(f"{sy}={a[sy]['acc']}" for sy in SYSTEMS))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--per-class", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--thresholds", type=float, nargs="+", default=[0.3, 0.5, 0.75])
    ap.add_argument("--weights", default=str(ROOT / "backend/services/ingestion/best.pt"))
    ap.add_argument("--ms2", default="http://localhost:8003")
    main(ap.parse_args())
