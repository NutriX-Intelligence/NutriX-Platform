"""
One-off MS3 data clean-up: remove one user and trim the community homely meals to the 3 starter dishes.

    PYTHONPATH=. python scripts/cleanup_ms3_data.py            # DRY RUN: shows what would be removed, changes nothing
    PYTHONPATH=. python scripts/cleanup_ms3_data.py --apply    # does it, in a single transaction (all or nothing)

By default it removes the account chaityadoshi23755@gmail.com (--email to change) with everything that belongs to the user
(profile, meal/water/weight logs, meal plans, settings, analytics, decisions), and deletes every homely meal except the
3 curated starters (Vada pav, Ghee Rice, Poha). Meals are deleted BEFORE the user: the database would otherwise only blank a
deleted user's meals' creator, leaving them as ownerless community meals visible to everybody.

Back the database up first:  docker exec nutrix-postgres pg_dump -U nutrix nutrix_db > backup_before_cleanup.sql
"""
import argparse

from sqlalchemy import text

from shared.db import SessionLocal

KEEP_MEALS = ("Vada pav", "Ghee Rice", "Poha")
USER_TABLES = ("profiles", "user_preferences", "goals", "meal_logs", "water_logs", "weight_logs", "recommendation_history",
               "analytics", "generated_meal_plans", "search_history", "settings", "user_adapters", "clinical_alerts",
               "clinical_reports", "homely_meal_decisions")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", default="chaityadoshi23755@gmail.com", help="account to remove")
    ap.add_argument("--apply", action="store_true", help="really delete (default: dry run)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        user = db.execute(text("SELECT id, name, email FROM users WHERE lower(email) = :e"), {"e": args.email.lower()}).fetchone()
        if user is None:
            print(f"No user with e-mail {args.email}; nothing to do for the user part.")
        else:
            print(f"USER to remove: id={user.id} {user.name} <{user.email}>")
            for t in USER_TABLES:
                n = db.execute(text(f"SELECT count(*) FROM {t} WHERE user_id = :u"), {"u": user.id}).scalar()
                if n:
                    print(f"   {t}: {n} row(s) will be removed with the user")
            n = db.execute(text("SELECT count(*) FROM audit_logs WHERE user_id = :u"), {"u": user.id}).scalar()
            if n:
                print(f"   audit_logs: {n} row(s) are kept, detached from the user")

        keep_sql = ", ".join(f":k{i}" for i in range(len(KEEP_MEALS)))
        keep_params = {f"k{i}": name for i, name in enumerate(KEEP_MEALS)}
        doomed = db.execute(
            text(f"SELECT id, name, creator_id, status FROM homely_meals "
                 f"WHERE NOT (creator_id IS NULL AND name IN ({keep_sql})) ORDER BY id"), keep_params).fetchall()
        kept = db.execute(
            text(f"SELECT id, name FROM homely_meals WHERE creator_id IS NULL AND name IN ({keep_sql}) ORDER BY id"), keep_params).fetchall()
        print(f"\nHOMELY MEALS to keep ({len(kept)}): " + ", ".join(f"#{r.id} {r.name}" for r in kept))
        print(f"HOMELY MEALS to delete ({len(doomed)}):")
        for r in doomed:
            print(f"   #{r.id} {r.name!r} (creator {r.creator_id}, {r.status})")
        if len(kept) != len(KEEP_MEALS):
            raise SystemExit(f"\nExpected the {len(KEEP_MEALS)} starter meals to exist but found {len(kept)}: stopping so nothing is lost.")

        if not args.apply:
            print("\nDRY RUN: nothing was changed. Re-run with --apply to do it.")
            return

        db.execute(text(f"DELETE FROM homely_meals WHERE NOT (creator_id IS NULL AND name IN ({keep_sql}))"), keep_params)
        if user is not None:
            db.execute(text("DELETE FROM users WHERE id = :u"), {"u": user.id})
        db.commit()
        print("\nDONE (committed).")

        if user is not None:  # his cached daily macros / streams (best effort: Redis is only a cache)
            try:
                from shared.redis_client import get_redis_client
                client = get_redis_client()
                keys = list(client.scan_iter(match=f"user:{user.id}:*")) if client else []
                if keys:
                    client.delete(*keys)
                print(f"Redis: removed {len(keys)} cached key(s) for user {user.id}.")
            except Exception as e:
                print(f"Redis: could not clear the cache ({e}); it is only a cache and expires on its own.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
