"""
FSN A3: list DB rows whose kcal/100 g looks wrong. Read-only on the DB; nothing is changed.

Rows compared with INDB (per 100 g):
  * the 31 Indian YOLO classes (brand 'YOLO Generic') through the v1 S4 crosswalk (scripts/fsn_s4_macro.CROSSWALK);
  * every other DB row (IND_FOOD_*, LLM Inferred, packaged snacks, ...) whose normalised name equals an INDB name, or the
    text in an INDB name's parentheses (e.g. 'Butter chicken (Murgh makhani)'); normalisation = lowercase, no
    punctuation, collapsed spaces. No fuzzy matching: unmatched rows are simply not compared.
A row is suspect if |DB kcal - INDB kcal| / INDB kcal > 50 %. The capture-related 'Mixed Nuts' row is always listed,
with USDA FDC SR Legacy mixed nuts as its reference (no INDB row), fetched through the FSN B3 cache.
Writes v2/suspect_db_rows.csv and v2/A3_db_vs_indb_all.csv (every compared row).

  PYTHONPATH=. python scripts/fsn_a3_suspect_rows.py
"""
import csv
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import text  # noqa: E402

import fsn_b3_fdc as fdc  # noqa: E402
from shared.db import SessionLocal  # noqa: E402
from shared.models import Food  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "paper-upgrade" / "results" / "fsn" / "v2"
INDB = ROOT / "dataset" / "ms3_datasets" / "INDB.xlsx"
THRESH = 0.5
MIXED_NUTS_FDC_QUERY = "nuts mixed nuts dry roasted with peanuts without salt added"


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


def indb_index(indb):
    idx = {}
    for code, name in zip(indb.index, indb.food_name):
        keys = {norm(re.sub(r"\(.*?\)", "", name))}
        keys |= {norm(p) for p in re.findall(r"\((.*?)\)", name)}
        for k in keys - {""}:
            idx.setdefault(k, []).append(code)
    return idx


def mixed_nuts_ref():
    c = fdc.Client()
    data = c.get("search_mixed_nuts_a3.json", "foods/search", {"query": MIXED_NUTS_FDC_QUERY, "dataType": "SR Legacy", "pageSize": 5})
    hit = next(h for h in data["foods"] if "mixed nuts" in h["description"].lower())
    d = c.get(f"food_{hit['fdcId']}.json", f"food/{hit['fdcId']}", {})
    return hit["fdcId"], d["description"], fdc.nutrient_values(d)


def main():
    from fsn_s4_macro import CROSSWALK
    indb = pd.read_excel(INDB).set_index("food_code")
    idx = indb_index(indb)
    cw = {norm(k): code for k, (_, code, _) in CROSSWALK.items()}
    db = SessionLocal()
    db.execute(text("SET TRANSACTION READ ONLY"))
    rows = []
    for f in db.query(Food).all():
        n = f.nutrients
        if n is None:
            continue
        key = norm(f.name)
        codes, how = [], ""
        if f.brand == "YOLO Generic" and key.replace(" ", "") in cw:
            codes, how = [cw[key.replace(" ", "")]], "S4 crosswalk (YOLO class)"
        elif key in idx:
            codes, how = idx[key], "exact normalised name"
        if not codes:
            continue
        if len(codes) > 1:
            how += f" ({len(codes)} INDB rows share the name; first used)"
        ref = indb.loc[codes[0]]
        db_k, ref_k = n.energy_kcal, float(ref["energy_kcal"])
        diff = (db_k - ref_k) / ref_k if (db_k is not None and ref_k > 0) else None
        rows.append(dict(food_id=f.id, food_code=f.food_code, name=f.name, brand=f.brand or "", created_at=f.created_at,
                         db_kcal=db_k, db_protein=n.protein_g, db_carbs=n.carb_g, db_fat=n.fat_g,
                         ref_source="INDB", ref_code=codes[0], ref_name=ref["food_name"], ref_kcal=ref_k,
                         ref_protein=float(ref["protein_g"]), ref_carbs=float(ref["carb_g"]), ref_fat=float(ref["fat_g"]),
                         match_rule=how, kcal_rel_diff=round(diff, 3) if diff is not None else "",
                         suspect=diff is not None and abs(diff) > THRESH,
                         note="DB energy is 0/null (now a lookup miss)" if not db_k else ""))
    mn = db.query(Food).filter(Food.food_code == "LLM_mixed_nuts").first()
    fid, fdesc, fv = mixed_nuts_ref()
    mrow = None
    if mn is not None:
        n = mn.nutrients
        d = (n.energy_kcal - fv["kcal"]) / fv["kcal"]
        mrow = dict(food_id=mn.id, food_code=mn.food_code, name=mn.name, brand=mn.brand or "", created_at=mn.created_at,
                    db_kcal=n.energy_kcal, db_protein=n.protein_g, db_carbs=n.carb_g, db_fat=n.fat_g,
                    ref_source="USDA FDC SR Legacy", ref_code=f"FDC_{fid}", ref_name=fdesc, ref_kcal=fv["kcal"],
                    ref_protein=fv["protein"], ref_carbs=fv["carbs"], ref_fat=fv["fat"], match_rule="manual (capture under audit)",
                    kcal_rel_diff=round(d, 3), suspect=abs(d) > THRESH,
                    note="persisted from the MS2 Qwen text lookup on 2026-10-30 (audit_logs llm_lookup, not flagged); "
                         "the Qwen vision answer for the same capture was flagged")
    db.rollback()
    with open(OUT / "A3_db_vs_indb_all.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    sus = ([mrow] if mrow else []) + sorted((r for r in rows if r["suspect"]), key=lambda r: -abs(r["kcal_rel_diff"]))
    with open(OUT / "suspect_db_rows.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sus)
    summ = {"n_db_rows_compared_with_indb": len(rows), "n_suspect_vs_indb": sum(r["suspect"] for r in rows),
            "n_zero_energy_among_compared": sum(1 for r in rows if not r["db_kcal"]),
            "by_rule": {k: sum(1 for r in rows if r["match_rule"].startswith(k)) for k in ("S4 crosswalk", "exact normalised name")},
            "mixed_nuts": {k: mrow[k] for k in ("db_kcal", "db_protein", "db_carbs", "db_fat", "ref_code", "ref_name", "ref_kcal", "kcal_rel_diff")} if mrow else None}
    (OUT / "suspect_db_rows_summary.json").write_text(json.dumps(summ, indent=2, default=str))
    print(json.dumps(summ, indent=2, default=str))
    for r in sus:
        print(f"  {r['food_code']:<16} {r['name'][:40]:<40} db {r['db_kcal']} vs {r['ref_code']} {r['ref_kcal']} ({r['kcal_rel_diff']})")


if __name__ == "__main__":
    main()
