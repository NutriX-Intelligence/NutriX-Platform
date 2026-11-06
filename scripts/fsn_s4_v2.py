"""
FSN B3 / S4 v2: macro-source ablation over INDB-scored Indian dishes (v1 crosswalk) + USDA-FDC-scored raw/other foods.

  collect : loads its OWN Qwen (stop MS2 first). For every scored food: (i) NutriX DB via shared.food_lookup (current
            rules), (ii) Qwen text lookup as emitted, (iii) after the Atwater recompute, (iv) (iii) if not flagged.
            Writes v2/S4_per_food.csv.
  report  : no GPU. Metrics (MAE, MAPE, median APE, Bland-Altman bias + 95% LoA) for kcal/protein/carbs/fat on
            all / Indian (INDB) / raw-other (USDA); suspect-INDB sensitivity (ref fat > 55 g/100 g) and a circularity
            sensitivity (DB row equal to the FDC value within 2 %, i.e. the DB row was copied from USDA). Writes
            v2/S4_metrics.csv, v2/S4_meta.json, v2/S4_summary.md.

  PYTHONPATH=. python scripts/fsn_s4_v2.py collect
  PYTHONPATH=. python scripts/fsn_s4_v2.py report
"""
import csv
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
V1 = ROOT / "docs" / "paper-upgrade" / "results" / "fsn"
OUT = V1 / "v2"
INDB = ROOT / "dataset" / "ms3_datasets" / "INDB.xlsx"
KEYS = [("kcal", "calories"), ("protein", "protein_g"), ("carbs", "carbs_g"), ("fat", "fat_g")]
SUSPECT_FAT = 55.0
WRONG_APE = 20.0
CIRCULAR_TOL = 0.02


def references():
    """food -> dict(ref_source, ref_code, ref_name, rule, query, ref_kcal..ref_fat)."""
    import pandas as pd
    from fsn_s4_macro import CROSSWALK
    indb = pd.read_excel(INDB).set_index("food_code")
    refs = {}
    for f, (q, code, rule) in CROSSWALK.items():
        row = indb.loc[code]
        refs[f] = dict(group="indian_indb", ref_source="INDB", ref_code=code, ref_name=row["food_name"],
                                                        rule=rule, query=q, ref_kcal=float(row["energy_kcal"]), ref_protein=float(row["protein_g"]),
                                                        ref_carbs=float(row["carb_g"]), ref_fat=float(row["fat_g"]))
    rule = {r["food"]: r["rule"] for r in csv.DictReader(open(OUT / "fdc_mapping.csv", newline=""))}
    for r in csv.DictReader(open(OUT / "fdc_reference_per100g.csv", newline="")):
        refs[r["food"]] = dict(group="raw_other_usda", ref_source=r["ref_source"], ref_code=r["ref_code"], ref_name=r["ref_name"],
                               rule=rule[r["food"]], query=r["food"], **{f"ref_{k}": float(r[f"ref_{k}"]) for k, _ in KEYS})
    return refs


def collect():
    from evaluate_post_llm import _raw_qwen_macros
    from ms2_llm import prompts
    from ms2_llm.validation import parse_nutrition
    from ms2_llm.vlm_engine import engine
    from shared.db import SessionLocal
    from shared.food_lookup import lookup_food_with_tier, per_100g
    from sqlalchemy import text

    refs = references()
    db = SessionLocal()
    db.execute(text("SET TRANSACTION READ ONLY"))
    engine.load()
    sys_p = prompts.get_system_prompt(prompts.LOOKUP_KEY)
    engine.infer(sys_p, prompts.lookup_user_prompt("rice"), None)          # warm-up, not scored
    recs = []
    for f, ref in refs.items():
        tier, food = lookup_food_with_tier(db, f)
        if food is None and ref["query"] != f:
            tier, food = lookup_food_with_tier(db, ref["query"])
        dbm = per_100g(food) if food else None
        raw = engine.infer(sys_p, prompts.lookup_user_prompt(ref["query"]), None)
        parsed = parse_nutrition(raw)
        rawm = _raw_qwen_macros(raw)
        pg = parsed["per_100g"] if parsed else None
        r = dict(food=f, **ref, db_tier=tier, db_food=food.name if food else "", db_brand=(food.brand or "") if food else "",
                 flagged=bool(parsed["flagged"]) if parsed else True,
                 flag_reason=(parsed or {}).get("flag_reason") or ("unparseable output" if not parsed else ""),
                 qwen_raw_text=raw.strip().replace("\n", " ")[:300])
        for k, dk in KEYS:
            r[f"db_{k}"] = dbm[dk] if dbm else None
            r[f"qraw_{k}"] = (rawm["raw_kcal"] if k == "kcal" else rawm[dk]) if rawm else None
            r[f"qatw_{k}"] = getattr(pg, dk) if pg is not None else None
        recs.append(r)
        print(f"{f}: ref {r['ref_kcal']:.0f} | db {r['db_kcal']} ({tier}) | qwen raw {r['qraw_kcal']} | atw {r['qatw_kcal']} | flagged {r['flagged']}", flush=True)
    db.rollback()
    with open(OUT / "S4_per_food.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0]))
        w.writeheader()
        w.writerows(recs)


# ── report ──────────────────────────────────────────────────────────────────────────────────────
num = lambda x: None if x in ("", None, "None") else float(x)


def metrics(est, ref):
    err = [e - r for e, r in zip(est, ref)]
    ape = [abs(e - r) / r * 100 for e, r in zip(est, ref) if r >= 1.0]       # APE undefined for reference < 1 g/100 g
    n = len(err)
    if not n:
        return None
    bias = sum(err) / n
    sd = st.stdev(err) if n > 1 else float("nan")
    return dict(n=n, MAE=round(sum(map(abs, err)) / n, 1), MAPE=round(sum(ape) / len(ape), 1) if ape else None,
                median_APE=round(st.median(ape), 1) if ape else None, n_APE=len(ape), BA_bias=round(bias, 1),
                LoA_lo=round(bias - 1.96 * sd, 1), LoA_hi=round(bias + 1.96 * sd, 1))


SOURCES = (("i DB", "db", False), ("ii Qwen raw", "qraw", False), ("iii Qwen Atwater", "qatw", False), ("iv Qwen after guardrail", "qatw", True))


def table(rows, label):
    md = [f"### {label} (n = {len(rows)} foods)", "", "| source | nutrient | n | MAE | MAPE % | median APE % | BA bias | 95% LoA |",
          "|---|---|---|---|---|---|---|---|"]
    out = []
    for name, pre, guard in SOURCES:
        for k, _ in KEYS:
            pr = [(num(r[f"{pre}_{k}"]), num(r[f"ref_{k}"])) for r in rows
                  if num(r[f"{pre}_{k}"]) is not None and not (guard and r["flagged"] == "True")]
            m = metrics([p[0] for p in pr], [p[1] for p in pr])
            if m:
                md.append(f"| {name} | {k} | {m['n']} | {m['MAE']} | {m['MAPE']} | {m['median_APE']} | {m['BA_bias']} | [{m['LoA_lo']}, {m['LoA_hi']}] |")
                out.append(dict(subset=label, source=name, nutrient=k, **m))
    return md + [""], out


def is_circular(r):
    """DB row equal to the reference (all 4 values within 2 % or 0.2 g): copied from the same table."""
    if num(r["db_kcal"]) is None:
        return False
    return all(abs(num(r[f"db_{k}"]) - num(r[f"ref_{k}"])) <= max(0.2, CIRCULAR_TOL * num(r[f"ref_{k}"])) for k, _ in KEYS)


def report():
    recs = list(csv.DictReader(open(OUT / "S4_per_food.csv", newline="")))
    for r in recs:
        r["suspect_indb"] = r["group"] == "indian_indb" and float(r["ref_fat"]) > SUSPECT_FAT
        r["db_equals_ref"] = is_circular(r)
    ind = [r for r in recs if r["group"] == "indian_indb"]
    raw = [r for r in recs if r["group"] == "raw_other_usda"]
    sets = [("All scored foods", recs), ("All scored foods, excluding suspect INDB rows", [r for r in recs if not r["suspect_indb"]]),
            ("Indian dishes (INDB)", ind), ("Indian dishes (INDB), excluding suspect rows", [r for r in ind if not r["suspect_indb"]]),
            ("Raw / other foods (USDA FDC SR Legacy)", raw),
            ("Raw / other foods (USDA), excluding DB rows equal to the USDA value", [r for r in raw if not r["db_equals_ref"]])]
    md_tables, rows = [], []
    for label, sub in sets:
        t, o = table(sub, label)
        md_tables += t
        rows += o
    with open(OUT / "S4_metrics.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    conf = {}
    for label, sub in (("all", recs), ("indian_indb", ind), ("raw_other_usda", raw)):
        c = {"wrong_flagged": 0, "wrong_not_flagged": 0, "correct_flagged": 0, "correct_not_flagged": 0}
        for r in sub:
            v = num(r["qatw_kcal"])
            if v is None:
                continue
            wrong = abs(v - float(r["ref_kcal"])) / float(r["ref_kcal"]) * 100 > WRONG_APE
            c[("wrong" if wrong else "correct") + ("_flagged" if r["flagged"] == "True" else "_not_flagged")] += 1
        conf[label] = c
    v1 = {r["food"]: r for r in csv.DictReader(open(V1 / "S4_per_food.csv", newline=""))}
    same_qwen = [r["food"] for r in ind if r["food"] in v1 and num(v1[r["food"]]["qatw_kcal"]) == num(r["qatw_kcal"])]
    meta = {"n_foods": len(recs), "n_indian_indb": len(ind), "n_raw_other_usda": len(raw),
            "suspect_indb_rows": [r["food"] for r in recs if r["suspect_indb"]],
            "db_rows_equal_to_usda_ref": [r["food"] for r in raw if r["db_equals_ref"]],
            "db_tier_counts": {t: sum(r["db_tier"] == t for r in recs) for t in ("exact", "alias", "partial", "miss")},
            "db_missing": [r["food"] for r in recs if num(r["db_kcal"]) is None],
            "n_flagged": sum(r["flagged"] == "True" for r in recs), "guardrail_confusion_atwater_kcal": conf,
            "wrong_definition": f"Qwen kcal (after Atwater) APE > {WRONG_APE}% vs reference",
            "indian_foods_with_same_qwen_kcal_as_v1": f"{len(same_qwen)} of {len(ind)}"}
    (OUT / "S4_meta.json").write_text(json.dumps(meta, indent=2))
    L = ["# S4 v2: macro-source ablation, INDB + USDA FDC (generated by scripts/fsn_s4_v2.py)", "",
         f"Foods scored: {len(recs)} = {len(ind)} Indian dishes vs INDB (v1 crosswalk) + {len(raw)} raw/other foods vs USDA FDC SR Legacy "
         "(mapping: fdc_mapping.csv; raw API responses: fdc_cache/). Values per 100 g. APE is undefined for reference < 1 g/100 g; "
         "those foods are dropped from MAPE/median APE only (n_APE in S4_metrics.csv).", "",
         f"DB values come from the current shared.food_lookup (partial tier off, empty rows = miss). DB tier counts: {meta['db_tier_counts']}; "
         f"no DB value for: {', '.join(meta['db_missing']) or 'none'}.", "",
         f"**Suspect INDB rows** (fat > {SUSPECT_FAT:g} g/100 g): {', '.join(meta['suspect_indb_rows'])}. Not corrected; tables with and without.", "",
         f"**Circularity:** {len(meta['db_rows_equal_to_usda_ref'])} of {len(raw)} raw/other DB rows equal the USDA reference (all four values within "
         f"{CIRCULAR_TOL:.0%} or 0.2 g): {', '.join(meta['db_rows_equal_to_usda_ref']) or 'none'}. For those foods the DB-vs-USDA error is not an "
         "independent accuracy measure; the last table drops them.", "",
         f"Qwen reproducibility: {meta['indian_foods_with_same_qwen_kcal_as_v1']} Indian foods got the same post-Atwater kcal as in v1.", ""]
    L += md_tables
    L += ["## Guardrail confusion (Qwen kcal after the Atwater recompute; wrong = APE > 20 % vs reference)", "",
          "| subset | wrong & flagged | wrong & not flagged | correct & flagged | correct & not flagged |", "|---|---|---|---|---|"]
    L += [f"| {k} | {c['wrong_flagged']} | {c['wrong_not_flagged']} | {c['correct_flagged']} | {c['correct_not_flagged']} |" for k, c in conf.items()]
    L += ["", f"Foods flagged in total: {meta['n_flagged']} of {len(recs)}.", ""]
    (OUT / "S4_summary.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    {"collect": collect, "report": report}[sys.argv[1]]()
