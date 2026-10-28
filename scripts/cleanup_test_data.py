"""
Remove junk meal_logs left by uncalibrated load-cell runs (negative / absurd weights or calories) and resync
Redis for every affected user/day. Dry-run by default.

    PYTHONPATH=. python scripts/cleanup_test_data.py                  # show what would be deleted
    PYTHONPATH=. python scripts/cleanup_test_data.py --apply          # delete it
    PYTHONPATH=. python scripts/cleanup_test_data.py --apply --legacy-source   # also every `esp32_smart_scale` row
"""
import argparse
from collections import defaultdict

from sqlalchemy import or_

from shared.db import SessionLocal
from shared.macro_sync import sync_daily_macros
from shared.models import MealLog

MAX_REASONABLE_WEIGHT_G = 10_000.0
MAX_REASONABLE_KCAL = 20_000.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    ap.add_argument("--legacy-source", action="store_true", help="also delete every row with source 'esp32_smart_scale'")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        conditions = [
            MealLog.weight_g <= 0, MealLog.weight_g > MAX_REASONABLE_WEIGHT_G,
            MealLog.calories < 0, MealLog.calories > MAX_REASONABLE_KCAL,
        ]
        if args.legacy_source:
            conditions.append(MealLog.source == "esp32_smart_scale")
        rows = db.query(MealLog).filter(or_(*conditions)).order_by(MealLog.id).all()

        print(f"{'ID':>5} | {'User':>4} | {'Date':10} | {'Food':18} | {'Weight g':>10} | {'kcal':>9} | Source")
        for m in rows:
            print(f"{m.id:>5} | {m.user_id:>4} | {m.log_date} | {(m.food_name or '')[:18]:18} | "
                  f"{(m.weight_g if m.weight_g is not None else float('nan')):>10.1f} | {m.calories or 0:>9.1f} | {m.source}")
        print(f"\n{len(rows)} row(s) match.")
        if not args.apply:
            print("Dry run: nothing deleted. Re-run with --apply to delete them.")
            return

        affected = defaultdict(set)
        for m in rows:
            affected[m.user_id].add(m.log_date)
            db.delete(m)
        db.commit()
        for user_id, days in affected.items():
            for day in days:
                sync_daily_macros(db, user_id, day, publish=False)
        print(f"Deleted {len(rows)} row(s); Redis resynced for {sum(len(d) for d in affected.values())} user/day pair(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
