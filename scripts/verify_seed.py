"""
Row counts for the seeded tables, plus the checks MS3 depends on.

    PYTHONPATH=. python scripts/verify_seed.py
"""
import sys

from sqlalchemy import text

from shared.db import SessionLocal

EXPECTED_FAST_FOOD = 3355
TABLES = ["users", "foods", "food_nutrients", "food_aliases", "unit_conversions", "recipes", "recipe_nutrition",
          "recipe_ingredients", "servings", "ingredient_rules", "homely_meals", "system_prompt_registry", "meal_logs"]


def main() -> int:
    db = SessionLocal()
    problems = []
    try:
        print("\n=== table row counts ===")
        for t in TABLES:
            try:
                print(f"  {t:26s} {db.execute(text(f'SELECT COUNT(*) FROM {t}')).scalar():>8,}")
            except Exception as e:
                db.rollback()
                print(f"  {t:26s} ERROR: {str(e).splitlines()[0][:70]}")
                problems.append(f"table {t} unreadable")

        print("\n=== fast food (recipes.brand) ===")
        rows = db.execute(text("SELECT brand, COUNT(*) FROM recipes WHERE brand IS NOT NULL GROUP BY brand ORDER BY brand")).fetchall()
        for brand, n in rows:
            print(f"  {brand:20s} {n:>6,}")
        total = sum(n for _, n in rows)
        print(f"  {'TOTAL':20s} {total:>6,}   (expected {EXPECTED_FAST_FOOD:,}, {len(rows)} chains)")
        if total != EXPECTED_FAST_FOOD:
            problems.append(f"fast food items {total} != {EXPECTED_FAST_FOOD}")

        print("\n=== recipes.dietary_tag (diet filters need every recipe tagged) ===")
        for tag, n in db.execute(text("SELECT COALESCE(dietary_tag, 'NULL'), COUNT(*) FROM recipes GROUP BY 1 ORDER BY 2 DESC")).fetchall():
            print(f"  {tag:20s} {n:>6,}")
        untagged = db.execute(text("SELECT COUNT(*) FROM recipes WHERE dietary_tag IS NULL")).scalar()
        if untagged:
            problems.append(f"{untagged} recipes have no dietary_tag")

        print("\n=== MS1 / MS2 food library ===")
        for brand, n in db.execute(text("SELECT COALESCE(brand, 'NULL'), COUNT(*) FROM foods GROUP BY 1 ORDER BY 2 DESC LIMIT 8")).fetchall():
            print(f"  {brand:20s} {n:>6,}")
    finally:
        db.close()

    print("\nRESULT:", "OK" if not problems else "PROBLEMS -> " + "; ".join(problems))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
