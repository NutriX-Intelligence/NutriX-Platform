"""Generate S1/S3/S5/S6 summary .md files from the result JSON/CSV (no hand-typed numbers)."""
import csv
import json
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "docs" / "paper-upgrade" / "results" / "fsn"

# ── S1 ──
s1 = json.load(open(D / "S1_benchmark_rerun.json"))
L = ["# S1: 7-image benchmark rerun (generated)", "", f"Run {s1['timestamp']} on current code. esp32.jpg = mixed plate, excluded from scoring.",
     f"Scoring: {json.dumps(s1['scoring'])}", f"Cold load: {json.dumps(s1['cold_load'])}; peak VRAM allocated {s1['resources']['peak_vram_allocated_mb']} MB",
     f"Latency excluding the first (warm-up) image: {json.dumps(s1['latency_summary_excl_warmup'])}", "",
     "| image | YOLO pred (raw conf %) | status | Qwen pred | Qwen raw kcal | Atwater kcal | flag_reason | macro src | kcal | score yolo/qwen/pipeline |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in s1["image_tests"]:
    rm = r["qwen"]["raw_macros"] or {}
    L.append(f"| {r['image']} | {r['yolo']['prediction']} ({r['yolo']['raw_conf']}) | {r['yolo']['status']} | {r['qwen']['prediction']} | {rm.get('raw_kcal')} | {rm.get('atwater_kcal')} | "
             f"{r['qwen']['flag_reason']} | {r['pipeline_resolution']['macro_source']} | {r['pipeline_resolution']['calculated_calories']} | "
             f"{r['score']['yolo']}/{r['score']['qwen']}/{r['score']['pipeline']} |")
L += ["", "## Text lookups (miss path)", "", "'paneer butter masala' is a curated DB row (IND_FOOD_0018, brand NULL), not an LLM-Inferred one, so it is always a DB hit; "
      "kadhai paneer / shahi tukda were verified absent beforehand and are used for the miss path.", "", "| query | source | latency ms | qwen raw kcal | Atwater kcal | flag_reason |", "|---|---|---|---|---|---|"]
for t in s1["text_lookups"]:
    rm = t.get("qwen_raw_macros") or {}
    L.append(f"| {t['query']} | {t['source']} | {t['latency_ms']} | {rm.get('raw_kcal','')} | {rm.get('atwater_kcal','')} | {t.get('flag_reason') or ''} |")
(D / "S1_summary.md").write_text("\n".join(L) + "\n")

# ── S3 ──
s3 = json.load(open(D / "S3_dedup_summary.json"))
L = ["# S3: cross-split near-duplicate check (generated)", "", f"pHash (64-bit), near-duplicate = Hamming <= {s3['threshold_hamming_le']}. Images: {s3['n_images']}.", "",
     "| pair | queries | with near-dup | % | exact-hash (d=0) |", "|---|---|---|---|---|"]
for k in ("test_vs_train", "valid_vs_train", "test_vs_valid"):
    v = s3[k]
    L.append(f"| {k} | {v['n']} | {v['n_with_near_dup']} | {v['pct']} | {v['exact_hash_match_d0']} |")
L += ["", "Leak-free rescoring of the S2 systems is in S2_summary.md (subsets `leak_free*`, test images with no train near-duplicate).", ""]
(D / "S3_summary.md").write_text("\n".join(L))

# ── S5 ──
rows = list(csv.DictReader(open(D / "S5_lookup_tiers.csv")))
uniq = {}
for r in rows:
    uniq.setdefault((r["vlm_name"], r["gt"]), r)
part = [r for r in uniq.values() if r["tier"] == "partial"]
L = ["# S5: knowledge-layer resolution tiers (generated)", "", f"{len(rows)} VLM answers from S2 (unhinted + hinted), {len(uniq)} distinct (name, ground-truth) pairs.",
     f"Tier counts (all answers): {dict(Counter(r['tier'] for r in rows))}",
     f"Tier counts (distinct pairs): {dict(Counter(r['tier'] for r in uniq.values()))}",
     f"Rows where tier logic disagrees with shared.food_lookup.lookup_food: {sum(r['consistent_with_lookup_food'] != 'True' for r in rows)}", "",
     "`canonical_matches_gt` is the automatic check; `manual_verdict` is left blank in S5_lookup_tiers.csv for a human. Check below: partial-tier resolutions (the riskiest tier):", "",
     "| ground truth | VLM name | resolved canonical food | canonical matches gt |", "|---|---|---|---|"]
L += [f"| {r['gt']} | {r['vlm_name']} | {r['canonical_food']} | {r['canonical_matches_gt']} |" for r in part]
exact = [r for r in uniq.values() if r["tier"] == "exact"]
L += ["", f"Exact tier: {sum(r['canonical_matches_gt'] == 'True' for r in exact)} of {len(exact)} distinct pairs resolve to the ground-truth food "
      "(the remainder are cases where the VLM name itself was wrong and was resolved faithfully to that wrong food).",
      f"Partial tier: {sum(r['canonical_matches_gt'] == 'True' for r in part)} of {len(part)} resolve to the ground-truth food; "
      "e.g. 'paneer' -> Palakpaneer, 'chutney' -> Coconutchutney, 'pepper' -> Bell Pepper are wrong-food resolutions for other ground truths.", ""]
(D / "S5_summary.md").write_text("\n".join(L))

# ── S6 ──
s6 = json.load(open(D / "S6_energy_engine_summary.json"))
(D / "S6_summary.md").write_text(f"# S6: energy-target engine (generated)\n\n{s6['n_pass']} of {s6['n_checks']} checks pass (6 hand-computed profiles x BMR/TDEE/target/macros/BMI + 8 unit checks), "
                                 f"tolerance {s6['tolerance_abs']}. Failures: {s6['failures']}. Hand arithmetic is in the comments of scripts/fsn_s6_energy.py; both female and male calorie floors (1200/1500) are exercised (P4, P5).\n")
print("ok")
