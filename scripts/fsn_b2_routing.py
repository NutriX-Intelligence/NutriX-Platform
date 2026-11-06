"""
FSN B2: pre-registered Indian-class routing rule.

Rule: at the main threshold T (0.5), a frame normally falls back to the VLM when YOLO conf < T (or the class is
suppressed). Routed variant: if YOLO's top-1 is one of the 31 Indian classes (and not suppressed) and its conf >= c,
keep YOLO's answer even below T. Otherwise fall back as usual (hinted VLM, knowledge-layer resolved = hybrid_resolved).

  tune     : VALIDATION split only (its leak-free subset vs train). Picks c in {0.1, 0.2, 0.3, 0.4} by best overall
             accuracy; ties -> the larger c (fewer overrides, closer to the unrouted pipeline). Writes routing_rule.json.
             Refuses to run if the test per-image file already exists, so the rule is fixed before test is touched.
  evaluate : test split, leak-free subset, exactly once (refuses if the result file exists). Needs routing_rule.json.

  PYTHONPATH=. python scripts/fsn_b2_routing.py tune
  PYTHONPATH=. python scripts/fsn_b2_routing.py evaluate
"""
import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_fallback_ablation as ab  # noqa: E402

OUT = ab.ROOT / "docs" / "paper-upgrade" / "results" / "fsn" / "v2"
THRESHOLD = 0.5
CANDIDATES = [0.1, 0.2, 0.3, 0.4]
VALID_CSV = OUT / "S2_per_image_valid_pc3_s0.csv"
TEST_CSV = OUT / "S2_per_image_test_pc3_s0.csv"
RULE = OUT / "routing_rule.json"
RESULT = OUT / "B2_routing_test_leakfree.json"


def load(path):
    rows = list(csv.DictReader(open(path, newline="")))
    for r in rows:
        r["yolo_conf"] = float(r["yolo_conf"])
        r["suppressed"] = r["suppressed"] == "True"
        r["leak_free"] = r["leak_free"] == "True"
        r["hybrid_vlm_canon"] = r.get("hybrid_vlm_canon") or ""
    return rows


def correct(r, c, indian, thr=THRESHOLD):
    """1/0 for hybrid_resolved with the routing rule (c=None -> no rule = plain hybrid_resolved)."""
    m, gt = ab.is_match, r["gt"]
    fallback = r["yolo_conf"] < thr or r["suppressed"]
    keep_yolo = (not fallback) or (c is not None and not r["suppressed"]
                                   and ab.clean_class_name(r["yolo"]) in indian and r["yolo_conf"] >= c)
    if keep_yolo:
        return float(m(r["yolo"], gt))
    return float(m(r["hybrid_vlm"], gt) or m(r["hybrid_vlm_canon"], gt))


def n_overridden(rows, c, indian, thr=THRESHOLD):
    return sum(1 for r in rows if (r["yolo_conf"] < thr and not r["suppressed"])
               and ab.clean_class_name(r["yolo"]) in indian and r["yolo_conf"] >= c)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def subsets(rows, indian):
    lf = [r for r in rows if r["leak_free"]]
    return {"leak_free": lf,
            "leak_free_indian": [r for r in lf if ab.clean_class_name(r["gt"]) in indian],
            "leak_free_other": [r for r in lf if ab.clean_class_name(r["gt"]) not in indian]}


def tune():
    if TEST_CSV.exists():
        sys.exit(f"refusing: {TEST_CSV.name} already exists; the rule must be chosen before the test split is scored")
    indian = ab.load_indian_classes()
    rows = [r for r in load(VALID_CSV) if r["leak_free"]]
    table = {}
    for c in CANDIDATES:
        acc, lo, hi = ab.bootstrap_ci([correct(r, c, indian) for r in rows])
        table[str(c)] = {"acc": round(acc, 4), "ci95": [round(lo, 4), round(hi, 4)], "n_overridden": n_overridden(rows, c, indian)}
    base, blo, bhi = ab.bootstrap_ci([correct(r, None, indian) for r in rows])
    best = max(CANDIDATES, key=lambda c: (table[str(c)]["acc"], c))         # ties -> larger c
    rule = {"rule": "if YOLO top-1 is an Indian class (not suppressed) and conf >= c, keep YOLO even below the main threshold; "
                    "otherwise fall back as usual (hybrid_resolved)",
            "main_threshold": THRESHOLD, "candidates": CANDIDATES, "selection": "best overall accuracy on VALIDATION leak-free; ties -> larger c",
            "chosen_c": best, "validation_leak_free_n": len(rows), "validation_per_c": table,
            "validation_no_rule_hybrid_resolved": {"acc": round(base, 4), "ci95": [round(blo, 4), round(bhi, 4)]},
            "validation_input": VALID_CSV.name, "validation_input_sha256": sha(VALID_CSV),
            "written_at": dt.datetime.now().isoformat(timespec="seconds"), "test_per_image_file_existed_at_write": TEST_CSV.exists(),
            "indian_classes": len(indian)}
    RULE.write_text(json.dumps(rule, indent=2))
    print(json.dumps(rule, indent=2))


def evaluate():
    if not RULE.exists():
        sys.exit("refusing: routing_rule.json missing (run tune first)")
    if RESULT.exists():
        sys.exit(f"refusing: {RESULT.name} exists; the test split is evaluated exactly once")
    rule = json.loads(RULE.read_text())
    c = rule["chosen_c"]
    indian = ab.load_indian_classes()
    out = {"chosen_c": c, "rule_file_sha256": sha(RULE), "test_input": TEST_CSV.name, "test_input_sha256": sha(TEST_CSV),
           "evaluated_at": dt.datetime.now().isoformat(timespec="seconds"), "subsets": {}}
    for name, sub in subsets(load(TEST_CSV), indian).items():
        routed = [correct(r, c, indian) for r in sub]
        plain = [correct(r, None, indian) for r in sub]
        yolo = [float(ab.is_match(r["yolo"], r["gt"])) for r in sub]
        e = {"n": len(sub), "n_overridden": n_overridden(sub, c, indian)}
        for k, v in (("hybrid_resolved_routed", routed), ("hybrid_resolved", plain), ("yolo_raw", yolo)):
            a, lo, hi = ab.bootstrap_ci(v)
            e[k] = {"acc": round(a, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        for k, other in (("routed_minus_hybrid_resolved", plain), ("routed_minus_yolo_raw", yolo)):
            d, lo, hi = ab.paired_diff_ci(routed, other)
            e[k] = {"diff": round(d, 4), "ci95": [round(lo, 4), round(hi, 4)]}
        out["subsets"][name] = e
    RESULT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    {"tune": tune, "evaluate": evaluate}[sys.argv[1]]()
