import sys
import os
from datetime import datetime, timezone

# Ensure project root is in path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def reset_session(user_id: int = 1, all_dates: bool = False):
    """
    Cleans up meal logs from PostgreSQL and clears the Redis macro cache
    for the specified user to start a clean test session.
    """
    today_date = datetime.now(timezone.utc).date()
    today_str = today_date.isoformat()

    print("\n" + "="*70)
    print(f"       NUTRIX TEST SESSION RESET — USER {user_id} ({today_str})")
    print("="*70)

    # 1. Reset PostgreSQL Meal Logs
    db_deleted_count = 0
    try:
        from shared.db import SessionLocal
        from shared.models import MealLog
        db = SessionLocal()
        try:
            query = db.query(MealLog).filter(MealLog.user_id == user_id)
            if not all_dates:
                query = query.filter(MealLog.log_date == today_date)
            db_deleted_count = query.delete(synchronize_session=False)
            db.commit()
            scope_str = "all dates" if all_dates else f"today ({today_str})"
            print(f"  [PostgreSQL] Deleted {db_deleted_count} MealLog entries for user {user_id} ({scope_str}).")
        except Exception as e:
            db.rollback()
            print(f"  [PostgreSQL Warning] Could not reset meal logs: {e}")
        finally:
            db.close()
    except Exception as e:
        print(f"  [PostgreSQL Warning] Database connection unavailable: {e}")

    # 2. Reset Redis Daily Macro Cache
    try:
        from shared.redis_client import get_redis_client, invalidate_daily_macros, set_daily_macros
        client = get_redis_client()
        if client:
            # Invalidate today's cache key
            invalidate_daily_macros(user_id, today_str)
            # Re-seed clean zero values
            zero_macro_data = {
                "user_id": user_id,
                "date": today_str,
                "calories": 0.0,
                "protein_g": 0.0,
                "carbs_g": 0.0,
                "fat_g": 0.0,
                "meals_count": 0,
                "latest_item": "None (Reset)"
            }
            set_daily_macros(user_id, today_str, zero_macro_data)
            print(f"  [Redis] Cache key 'user:{user_id}:macros:{today_str}' reset to 0.0 kcal.")
        else:
            print(f"  [Redis Warning] Redis client not connected (in fallback mode).")
    except Exception as e:
        print(f"  [Redis Warning] Redis cache reset failed: {e}")

    print("-" * 70)
    print("  Status: Clean session ready. New captures will start from 0 kcal.")
    print("="*70 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reset NutriX test session data in Postgres and Redis.")
    parser.add_argument("--user-id", type=int, default=1, help="User ID to reset (default: 1)")
    parser.add_argument("--all-dates", action="store_true", help="Delete all historical meal logs for this user, not just today")
    args = parser.parse_args()

    reset_session(user_id=args.user_id, all_dates=args.all_dates)
