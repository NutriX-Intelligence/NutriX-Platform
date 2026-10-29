"""
Retag the home-style recipe library from its ingredients so Jain / vegan / vegetarian filters work.

    PYTHONPATH=. python scripts/retag_recipes.py            # DRY RUN: shows before/after and examples, changes nothing
    PYTHONPATH=. python scripts/retag_recipes.py --apply    # writes the new tags

Fast-food items keep the tag the chain published. Restart MS3 afterwards: the recommendation engine caches each recipe's
tag in memory.
"""
import argparse
import logging

from shared.db import SessionLocal
from ms3_user.services.recipe_tagging import retag_recipes

ORDER = ["Jain", "Vegan", "Vegetarian", "Eggetarian", "Pescatarian", "Non-Vegetarian", "NULL"]


def main() -> None:
    logging.disable(logging.CRITICAL)
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the new tags (default: dry run)")
    ap.add_argument("--only-untagged", action="store_true", help="leave recipes that already have a tag alone")
    ap.add_argument("--examples", type=int, default=4, help="example recipes to show per new tag")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        result = retag_recipes(db, apply=args.apply, only_untagged=args.only_untagged)
        print(f"\n{result['total']} home-style recipes (fast-food items are not touched)\n")
        print(f"{'tag':16} {'before':>7} {'after':>7}")
        for tag in ORDER:
            b, a = result["before"].get(tag, 0), result["after"].get(tag, 0)
            if b or a:
                print(f"{tag:16} {b:7d} {a:7d}")

        changes = result["changes"]
        print(f"\n{len(changes)} recipe(s) change tag.")
        by_new = {}
        for code, name, old, new, reason in changes:
            by_new.setdefault(new, []).append((name, old))
        for tag in ORDER:
            rows = by_new.get(tag, [])
            if rows:
                shown = "; ".join(f"{n} (was {o})" for n, o in rows[: args.examples])
                print(f"  -> {tag} ({len(rows)}): {shown}")

        conflicts = result["conflicts"]
        if conflicts:
            print(f"\n{len(conflicts)} regional recipe(s) where the curated tag contradicts the ingredients (the safer, ingredient-based tag was used):")
            for code, name, declared, classified in conflicts[:8]:
                print(f"  {name}: declared {declared}, ingredients say {classified}")

        print("\nAPPLIED. Restart MS3 (the engine caches tags in memory)." if args.apply
              else "\nDRY RUN: nothing was written. Re-run with --apply to save these tags (back up the database first).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
