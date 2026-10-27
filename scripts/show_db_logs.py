import sys
from shared.db import SessionLocal
from shared.models import MealLog, User, Food

def main():
    db = SessionLocal()
    try:
        logs = db.query(MealLog).order_by(MealLog.id.desc()).limit(15).all()
        print("\n" + "="*86)
        print("          NUTRIX POSTGRESQL — LATEST SCALE MEAL LOGS")
        print("="*86)
        if not logs:
            print("No meal logs found yet. Press the ESP32 button to record a meal!")
        else:
            print(f"{'ID':<5} | {'Food Name':<18} | {'Weight':<10} | {'Calories':<12} | {'Source':<14} | {'Logged Date'}")
            print("-" * 86)
            for m in logs:
                print(f"#{m.id:<4} | {m.food_name:<18} | {m.weight_g or 0:>6.1f} g  | {m.calories:>6.1f} kcal | {(m.source or '-'):<14} | {m.log_date}")
        print("="*86 + "\n")
    finally:
        db.close()

if __name__ == "__main__":
    main()
