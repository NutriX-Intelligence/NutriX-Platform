"""
FSN A1: how many of the v1 S5 VLM names change resolution under the new lookup rules.

Both rules run on the SAME current DB, so only the rule differs:
  old         = the v1 rule (exact -> alias -> any trusted-brand substring match; empty rows only lose to complete ones)
  new_default = shared.food_lookup with FOOD_LOOKUP_PARTIAL unset (partial tier off)            <- app default
  new_partial = shared.food_lookup with FOOD_LOOKUP_PARTIAL=true (>= 2 words, >= 80 % coverage)
Read-only on the DB.   PYTHONPATH=. python scripts/fsn_a1_partial_changes.py
"""
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_fallback_ablation as ab  # noqa: E402
from sqlalchemy import text  # noqa: E402

from shared.db import SessionLocal  # noqa: E402
from shared.food_lookup import (TRUSTED_PARTIAL_BRANDS, _escape_like, lookup_food_with_tier,  # noqa: E402
                                normalize_name)
from shared.models import Food, FoodAlias  # noqa: E402

V1 = ab.ROOT / "docs" / "paper-upgrade" / "results" / "fsn"
OUT = V1 / "v2"


def _old_first(foods):
    foods = list(foods)
    has = lambda f: f.nutrients is not None and ((f.nutrients.energy_kcal or 0) > 0 or
                                                  (f.nutrients.protein_g or 0) + (f.nutrients.carb_g or 0) + (f.nutrients.fat_g or 0) > 0)
    return next((f for f in foods if has(f)), foods[0] if foods else None)


def old_rule(db, name):
    clean = normalize_name(name)
    if not clean or clean in ("unknown", "error"):
        return "miss", None
    f = _old_first(db.query(Food).filter(Food.name.ilike(_escape_like(clean), escape="\\")).all())
    if f:
        return "exact", f
    f = _old_first(a.food for a in db.query(FoodAlias).filter(FoodAlias.alias_name.ilike(_escape_like(clean), escape="\\")).all())
    if f:
        return "alias", f
    f = _old_first(db.query(Food).filter(Food.name.ilike(f"%{_escape_like(clean)}%", escape="\\"),
                                         Food.brand.in_(TRUSTED_PARTIAL_BRANDS)).all())
    return ("partial", f) if f else ("miss", None)


def new_rule(db, name, partial):
    os.environ["FOOD_LOOKUP_PARTIAL"] = "true" if partial else "false"
    clean = normalize_name(name)
    if not clean or clean in ("unknown", "error"):
        return "miss", None
    return lookup_food_with_tier(db, name)


def main():
    v1 = list(csv.DictReader(open(V1 / "S5_lookup_tiers.csv", newline="")))
    pairs = {}
    for r in v1:
        pairs.setdefault((r["vlm_name"], r["gt"]), r)
    db = SessionLocal()
    db.execute(text("SET TRANSACTION READ ONLY"))
    saved = os.environ.get("FOOD_LOOKUP_PARTIAL")
    rows = []
    for (name, gt), r in sorted(pairs.items()):
        o = old_rule(db, name)
        d = new_rule(db, name, False)
        p = new_rule(db, name, True)
        fname = lambda t: t[1].name if t[1] else ""
        rows.append(dict(vlm_name=name, gt=gt, v1_tier=r["tier"], v1_food=r["canonical_food"],
                         old_tier=o[0], old_food=fname(o), new_default_tier=d[0], new_default_food=fname(d),
                         new_partial_tier=p[0], new_partial_food=fname(p),
                         changed_default=(o[1].id if o[1] else None) != (d[1].id if d[1] else None),
                         changed_partial_on=(o[1].id if o[1] else None) != (p[1].id if p[1] else None),
                         old_matches_gt=bool(o[1]) and ab.is_match(fname(o), gt),
                         new_default_matches_gt=bool(d[1]) and ab.is_match(fname(d), gt)))
    db.rollback()
    if saved is None:
        os.environ.pop("FOOD_LOOKUP_PARTIAL", None)
    else:
        os.environ["FOOD_LOOKUP_PARTIAL"] = saved
    with open(OUT / "A1_partial_rule_changes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    distinct_names = {r["vlm_name"] for r in rows}
    ch = [r for r in rows if r["changed_default"]]
    summ = {"n_distinct_name_gt_pairs": len(rows), "n_distinct_names": len(distinct_names),
            "old_tier_counts": dict(Counter(r["old_tier"] for r in rows)),
            "new_default_tier_counts": dict(Counter(r["new_default_tier"] for r in rows)),
            "new_partial_on_tier_counts": dict(Counter(r["new_partial_tier"] for r in rows)),
            "pairs_changed_default": len(ch), "names_changed_default": len({r["vlm_name"] for r in ch}),
            "pairs_changed_partial_on": sum(r["changed_partial_on"] for r in rows),
            "changed_by_old_tier": dict(Counter(r["old_tier"] for r in ch)),
            "old_partial_pairs_correct": sum(r["old_matches_gt"] for r in rows if r["old_tier"] == "partial"),
            "old_partial_pairs": sum(r["old_tier"] == "partial" for r in rows),
            "v1_vs_old_rule_tier_disagreements": sum(r["v1_tier"] != r["old_tier"] for r in rows)}
    (OUT / "A1_partial_rule_changes.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=2))
    for r in ch:
        print(f"  {r['vlm_name']!r} (gt {r['gt']}): {r['old_tier']} {r['old_food']!r} -> {r['new_default_tier']} {r['new_default_food']!r}")


if __name__ == "__main__":
    main()
