"""
FSN A2: why were 'Oreo' / 'Chocolate Bar' logged as 0 kcal in the demo? Read-only evidence dump.

Collects: meal_logs rows for oreo / chocolate / nuts and every 0 kcal scale row; the MS2 audit_logs answers for the
same foods; the foods rows those names resolve to (old v1 rule vs current lookup); counts of foods rows with null/0
energy. Writes v2/A2_zero_kcal_investigation.json.   PYTHONPATH=. python scripts/fsn_a2_investigate.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import String, cast, func, or_, text  # noqa: E402

from fsn_a1_partial_changes import old_rule  # noqa: E402
from shared.db import SessionLocal  # noqa: E402
from shared.food_lookup import lookup_food_with_tier  # noqa: E402
from shared.models import AuditLog, Food, FoodNutrient, MealLog  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "paper-upgrade" / "results" / "fsn" / "v2"
KEYS = ("oreo", "chocolate", "nut")


def food_dict(f):
    if f is None:
        return None
    n = f.nutrients
    return dict(id=f.id, food_code=f.food_code, name=f.name, brand=f.brand, created_at=str(f.created_at),
                kcal=n and n.energy_kcal, protein=n and n.protein_g, carbs=n and n.carb_g, fat=n and n.fat_g)


def main():
    db = SessionLocal()
    db.execute(text("SET TRANSACTION READ ONLY"))
    logs = db.query(MealLog).filter(or_(MealLog.calories == 0, *[MealLog.food_name.ilike(f"%{k}%") for k in KEYS])).order_by(MealLog.id)
    s = cast(AuditLog.output_summary, String)
    audit = db.query(AuditLog).filter(or_(*[s.ilike(f"%{k}%") for k in KEYS])).order_by(AuditLog.id)
    same_name = {n: [food_dict(f) for f in db.query(Food).filter(Food.name.ilike(n)).order_by(Food.id)] for n in ("oreo", "chocolate bar", "mixed nuts")}
    zero = or_(FoodNutrient.energy_kcal.is_(None), FoodNutrient.energy_kcal == 0)
    out = {
        "meal_logs": [dict(id=m.id, log_date=str(m.log_date), food_name=m.food_name, meal_type=m.meal_type, weight_g=m.weight_g,
                           calories=m.calories, protein=m.protein, carbs=m.carbs, fat=m.fat, source=m.source) for m in logs],
        "audit_logs": [dict(id=a.id, created_at=str(a.created_at), service=a.service, operation=a.operation, flagged=a.flagged,
                            output=a.output_summary) for a in audit],
        "foods_with_exact_name": same_name,
        "resolution": {n: {"v1_rule": dict(zip(("tier", "food"), (lambda t: (t[0], food_dict(t[1])))(old_rule(db, n)))),
                           "current": dict(zip(("tier", "food"), (lambda t: (t[0], food_dict(t[1])))(lookup_food_with_tier(db, n))))}
                       for n in ("oreo", "chocolate bar", "mixed nuts")},
        "foods_total": db.query(Food).count(),
        "foods_with_null_or_zero_energy": db.query(Food).join(FoodNutrient).filter(zero).count(),
        "foods_with_null_or_zero_energy_but_macros": db.query(Food).join(FoodNutrient).filter(
            zero, (func.coalesce(FoodNutrient.protein_g, 0) + func.coalesce(FoodNutrient.carb_g, 0) + func.coalesce(FoodNutrient.fat_g, 0)) > 0).count(),
        "note": "the v1 rule here is the lookup as of commit b247304 (empty rows lose only to complete rows); "
                "at the demo (commit a076b2e, 2026-10-29) the exact tier used .first() with no ordering, so the all-zero "
                "'OREO' row could win outright.",
    }
    db.rollback()
    (OUT / "A2_zero_kcal_investigation.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({k: v for k, v in out.items() if k not in ("audit_logs", "meal_logs")}, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
