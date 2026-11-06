"""
S4: macro-source ablation against INDB (per 100 g).

Estimates per food:  (i) NutriX DB (shared.food_lookup.lookup_macros)  (ii) Qwen text lookup as emitted, DB bypassed
(iii) Qwen after the Atwater recompute in ms2_llm.validation.parse_nutrition  (iv) (iii) only if the guardrail did not flag it.

Loads its own Qwen: MS2 must be stopped (6 GB GPU).   PYTHONPATH=. python scripts/fsn_s4_macro.py
The food -> INDB crosswalk is the CROSSWALK table below; it is written out in S4_crosswalk.csv for human audit.
Foods without an INDB row are NOT scored (no reference available locally) and are listed with the reason.
"""
import csv
import json
import statistics as st
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import eval_fallback_ablation as ab  # noqa: E402
from evaluate_post_llm import _raw_qwen_macros  # noqa: E402
from ms2_llm import prompts  # noqa: E402
from ms2_llm.validation import extract_json, parse_nutrition  # noqa: E402
from ms2_llm.vlm_engine import engine  # noqa: E402
from shared.db import SessionLocal  # noqa: E402
from shared.food_lookup import lookup_macros  # noqa: E402

OUT = ROOT / "docs" / "paper-upgrade" / "results" / "fsn"
INDB = ROOT / "dataset" / "ms3_datasets" / "INDB.xlsx"
WRONG_APE = 20.0

# class name -> (query name given to Qwen, INDB food_code, rule). Rules: exact | transliteration | synonym |
# generic->variant (class is generic, INDB has several variants; the most common one was picked: a JUDGEMENT to audit).
CROSSWALK = {
    "aloogobi": ("aloo gobi", "ASC171", "transliteration"),
    "bhatura": ("bhatura", "ASC143", "exact"),
    "chai": ("chai", "ASC001", "synonym (parenthetical 'Garam Chai')"),
    "chole": ("chole", "ASC162", "synonym (chickpea curry) - judgement"),
    "dosa": ("dosa", "BFP148", "generic->variant (plain dosa) - judgement"),
    "idli": ("idli", "ASC144", "exact"),
    "kheer": ("kheer", "ASC282", "generic->variant (rice kheer) - judgement"),
    "kulfi": ("kulfi", "ASC321", "exact"),
    "onionpakoda": ("onion pakoda", "ASC352", "transliteration"),
    "palakpaneer": ("palak paneer", "ASC215", "exact (parenthetical)"),
    "poha": ("poha", "BFP044", "exact"),
    "rajmacurry": ("rajma curry", "ASC165", "exact (parenthetical)"),
    "rasmalai": ("rasmalai", "BFP393", "exact"),
    "samosa": ("samosa", "ASC361", "generic->variant (potato samosa) - judgement"),
    "shahipaneer": ("shahi paneer", "ASC221", "exact"),
}
AMBIGUOUS = {"lassi": "INDB has sweet and salted lassi", "gulabjamun": "INDB has khoya and milk-powder variants",
             "biryani": "INDB has mutton and vegetable biryani", "kebab": "INDB has >=6 kebab variants"}
KEYS = [("kcal", "energy_kcal", "calories"), ("protein", "protein_g", "protein_g"),
        ("carbs", "carb_g", "carbs_g"), ("fat", "fat_g", "fat_g")]


def food_set():
    rows = list(csv.DictReader(open(OUT / "S2_per_image_test_pc3_s0.csv")))
    foods = {ab.clean_class_name(r["gt"]) for r in rows if r["hybrid_resolved_t0.5"] == "1" or r["yolo_raw_t0.5"] == "1"}
    foods |= {"apple", "banana", "tomato", "watermelon", "sweet potato", "idli"}      # S1 correct identifications
    foods |= {ab.clean_class_name(c) for c in ab.load_indian_classes()}               # the 31 Indian classes
    return sorted(foods), {ab.clean_class_name(c) for c in ab.load_indian_classes()}


def metrics(est, ref):
    err = [e - r for e, r in zip(est, ref)]
    ape = [abs(e - r) / r * 100 for e, r in zip(est, ref) if r >= 1.0]       # APE undefined for reference < 1 g/100 g
    n = len(err)
    if not n:
        return {"n": 0}
    bias = sum(err) / n
    sd = st.stdev(err) if n > 1 else float("nan")
    return {"n": n, "MAE": round(sum(abs(e) for e in err) / n, 2),
            "MAPE_pct": round(sum(ape) / len(ape), 1) if ape else None,
            "median_APE_pct": round(st.median(ape), 1) if ape else None, "n_APE": len(ape),
            "BA_bias": round(bias, 2), "BA_loa_lo": round(bias - 1.96 * sd, 2), "BA_loa_hi": round(bias + 1.96 * sd, 2)}


def main():
    foods, indian = food_set()
    indb = pd.read_excel(INDB).set_index("food_code")
    db = SessionLocal()
    engine.load()
    sys_p = prompts.get_system_prompt(prompts.LOOKUP_KEY)
    engine.infer(sys_p, prompts.lookup_user_prompt("rice"), None)          # warm-up, not scored

    cw_rows, recs = [], []
    for f in foods:
        key = f.replace(" ", "")
        hit = CROSSWALK.get(f) or CROSSWALK.get(key)
        if hit is None:
            reason = ("ambiguous_multiple_variants: " + AMBIGUOUS[f]) if f in AMBIGUOUS else \
                ("no INDB row found (Indian class)" if f in indian else "raw/non-Indian food: not in INDB, no USDA reference file available locally")
            cw_rows.append(dict(food=f, indian_class=f in indian, ref_source="none", ref_code="", ref_name="", rule="", status=reason))
            continue
        q, code, rule = hit
        ref = indb.loc[code]
        cw_rows.append(dict(food=f, indian_class=f in indian, ref_source="INDB", ref_code=code, ref_name=ref["food_name"],
                            rule=rule, status="scored"))
        db_m = lookup_macros(db, f) or lookup_macros(db, q)
        raw = engine.infer(sys_p, prompts.lookup_user_prompt(q), None)
        parsed = parse_nutrition(raw)
        rawm = _raw_qwen_macros(raw)
        r = dict(food=f, query=q, ref_code=code, rule=rule, qwen_raw_text=raw.strip().replace("\n", " ")[:300],
                 flagged=bool(parsed["flagged"]) if parsed else True,
                 flag_reason=(parsed or {}).get("flag_reason") or "unparseable output",
                 db_found=db_m is not None)
        for k, col, dk in KEYS:
            r[f"ref_{k}"] = float(ref[col])
            r[f"db_{k}"] = db_m[dk] if db_m else None
        for k, _, dk in KEYS:
            r[f"qraw_{k}"] = (rawm["raw_kcal"] if k == "kcal" else rawm[dk]) if rawm else None
            pg = parsed["per_100g"] if parsed else None
            r[f"qatw_{k}"] = getattr(pg, dk) if pg is not None else None
        recs.append(r)
        print(f"{f}: ref {r['ref_kcal']:.0f} kcal | db {r['db_kcal']} | qwen raw {r['qraw_kcal']} | atw {r['qatw_kcal']} | flagged {r['flagged']}", flush=True)

    with open(OUT / "S4_crosswalk.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cw_rows[0]))
        w.writeheader()
        w.writerows(cw_rows)
    with open(OUT / "S4_per_food.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)

    # metrics per source and nutrient
    sources = {"i_db": "db", "ii_qwen_raw": "qraw", "iii_qwen_atwater": "qatw"}
    summ_rows = []
    for name, pre in list(sources.items()) + [("iv_qwen_after_guardrail", "qatw")]:
        for k, _, _ in KEYS:
            pairs = [(r[f"{pre}_{k}"], r[f"ref_{k}"]) for r in recs
                     if r[f"{pre}_{k}"] is not None and not (name.startswith("iv") and r["flagged"])]
            m = metrics([p[0] for p in pairs], [p[1] for p in pairs])
            summ_rows.append(dict(source=name, nutrient=k, n_foods_with_value=m["n"], n_foods_total=len(recs), **{x: y for x, y in m.items() if x != "n"}))
    with open(OUT / "S4_macro_source.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summ_rows[0]))
        w.writeheader()
        w.writerows(summ_rows)

    # guardrail confusion on the post-recompute kcal (what would be accepted): wrong = kcal APE > 20 %
    conf = {"wrong_flagged": 0, "wrong_not_flagged": 0, "correct_flagged": 0, "correct_not_flagged": 0}
    conf_raw = dict(conf)
    for r in recs:
        for tag, c, pre in (("atw", conf, "qatw"), ("raw", conf_raw, "qraw")):
            v = r[f"{pre}_kcal"]
            if v is None:
                continue
            wrong = abs(v - r["ref_kcal"]) / r["ref_kcal"] * 100 > WRONG_APE
            c[("wrong" if wrong else "correct") + ("_flagged" if r["flagged"] else "_not_flagged")] += 1
    meta = {"n_foods_scored": len(recs), "n_foods_total": len(foods), "n_unscored": len(foods) - len(recs),
            "wrong_definition": f"kcal APE > {WRONG_APE}% vs INDB", "guardrail_confusion_on_atwater_kcal": conf,
            "guardrail_confusion_on_raw_kcal": conf_raw, "n_flagged": sum(r["flagged"] for r in recs),
            "db_missing_for_scored_foods": [r["food"] for r in recs if not r["db_found"]]}
    (OUT / "S4_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
