"""
Create (or update) a login-capable development account, by default user id 1: the id the scale
simulator (`dev_capture.py --user-id 1`) and the firmware send. Afterwards the same account can sign in
through the gateway/app, and everything the scale logs shows up on that account's dashboard.

    PYTHONPATH=. python scripts/create_dev_user.py
    PYTHONPATH=. python scripts/create_dev_user.py --id 1 --email me@example.com --password secret123 --name "Harsh"
"""
import argparse

from sqlalchemy import text

from shared.db import SessionLocal
from shared.models import User
from ms3_user.services.auth_service import hash_password
from ms3_user.services.nutrition_engine import NutritionEngine


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, default=1)
    ap.add_argument("--email", default="dev@nutrix.dev")
    ap.add_argument("--password", default="nutrix123")
    ap.add_argument("--name", default="Dev User")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        targets = NutritionEngine.calculate_targets(
            age=25, gender="male", height=170.0, weight=70.0, activity_level="sedentary", goal="maintenance")
        user = db.query(User).filter(User.id == args.id).first()
        created = user is None
        if created:
            user = User(id=args.id, name=args.name, email=args.email.lower())
            db.add(user)
        user.name = args.name
        user.email = args.email.lower()
        user.hashed_password = hash_password(args.password)
        user.is_active = True
        if user.target_calories is None:  # first time: give the account sensible targets so the rings render
            user.age, user.gender, user.height, user.weight = 25, "male", 170.0, 70.0
            user.activity_level, user.goal = "sedentary", "maintenance"
            user.target_calories = targets["target_calories"]
            user.target_protein = targets["target_protein_g"]
            user.target_carbs = targets["target_carbs_g"]
            user.target_fat = targets["target_fat_g"]
            user.water_target_ml = targets["water_target_ml"]
        db.commit()
        try:  # an explicit id does not advance the serial sequence; without this the next registration collides
            db.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT GREATEST(MAX(id), 1) FROM users))"))
            db.commit()
        except Exception:
            db.rollback()
        print(f"{'Created' if created else 'Updated'} user #{user.id}: {user.email} (password: {args.password})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
