"""S6: check ms3_user NutritionEngine against hand-computed Mifflin-St Jeor / TDEE / goal-adjusted targets.

Expected values below were worked out by hand (comments show the arithmetic), NOT by calling the engine.
Macro grams use the engine's documented goal splits and 4/4/9 kcal/g; expected macros are derived from the
hand-computed target kcal.
"""
import csv
import json
from pathlib import Path

from ms3_user.services.nutrition_engine import NutritionEngine, normalize_goal

OUT = Path(__file__).resolve().parent.parent / "docs" / "paper-upgrade" / "results" / "fsn"
SPLITS = {"fat loss": (.30, .40, .30), "weight gain": (.25, .50, .25),
          "muscle gain": (.30, .45, .25), "maintenance": (.25, .45, .30)}

# id, age, sex, height_cm, weight_kg, activity, goal, hand BMR, hand TDEE, hand target, note
CASES = [
    # 10*70 + 6.25*175 - 5*25 + 5 = 700 + 1093.75 - 125 + 5 = 1673.75 ; x1.2 = 2008.5
    ("P1", 25, "male", 175, 70, "sedentary", "maintenance", 1673.75, 2008.5, 2008.5, "baseline male"),
    # 600 + 1031.25 - 150 - 161 = 1320.25 ; x1.375 = 1815.34375 ; -500 = 1315.34 (> 1200 floor)
    ("P2", 30, "female", 165, 60, "lightly_active", "fat loss", 1320.25, 1815.34, 1315.34, "deficit, floor not hit"),
    # 900 + 1125 - 200 + 5 = 1830 ; x1.55 = 2836.5 ; +300 = 3136.5
    ("P3", 40, "male", 180, 90, "moderately_active", "muscle gain", 1830.0, 2836.5, 3136.5, "surplus +300"),
    # 500 + 968.75 - 110 - 161 = 1197.75 ; x1.2 = 1437.3 ; -500 = 937.3 -> female floor 1200
    ("P4", 22, "female", 155, 50, "sedentary", "fat loss", 1197.75, 1437.3, 1200.0, "female floor 1200 applied"),
    # 650 + 1062.5 - 275 + 5 = 1442.5 ; x1.2 = 1731 ; -500 = 1231 -> male floor 1500
    ("P5", 55, "male", 170, 65, "sedentary", "fat loss", 1442.5, 1731.0, 1500.0, "male floor 1500 applied"),
    # 720 + 1050 - 175 - 161 = 1434 ; x1.9 = 2724.6 ; +500 = 3224.6
    ("P6", 35, "female", 168, 72, "very_active", "weight gain", 1434.0, 2724.6, 3224.6, "surplus +500"),
]
TOL = 0.011  # engine rounds to 2 dp

rows, failures = [], []
for pid, age, sex, h, w, act, goal, e_bmr, e_tdee, e_target, note in CASES:
    r = NutritionEngine.calculate_targets(age, sex, h, w, act, goal)
    p, c, f = SPLITS[goal]
    exp = {"bmr": e_bmr, "tdee": e_tdee, "target_calories": e_target,
           "target_protein_g": round(e_target * p / 4, 2), "target_carbs_g": round(e_target * c / 4, 2),
           "target_fat_g": round(e_target * f / 9, 2), "bmi": round(w / (h / 100) ** 2, 2)}
    for k, v in exp.items():
        ok = abs(r[k] - v) <= TOL
        rows.append(dict(profile=pid, age=age, sex=sex, height_cm=h, weight_kg=w, activity=act, goal=goal,
                         quantity=k, hand_computed=v, engine=r[k], abs_diff=round(abs(r[k] - v), 4),
                         pass_=ok, note=note))
        if not ok:
            failures.append((pid, k, v, r[k]))

# direct unit-level checks: unknown activity -> 1.2, goal wording normalisation, unknown-sex branch
extra = [
    ("tdee_unknown_activity_uses_1.2", NutritionEngine.calculate_tdee(1000, "couch"), 1200.0),
    ("tdee_active_1.725", NutritionEngine.calculate_tdee(1000, "active"), 1725.0),
    ("goal 'weight loss' -> fat loss", normalize_goal("weight loss"), "fat loss"),
    ("goal 'lose_weight' -> fat loss", normalize_goal("lose_weight"), "fat loss"),
    ("goal 'bulk' -> muscle gain", normalize_goal("bulk"), "muscle gain"),
    ("goal 'gain weight' -> weight gain", normalize_goal("gain weight"), "weight gain"),
    ("goal 'xyz' -> maintenance", normalize_goal("xyz"), "maintenance"),
    ("bmi height 0 -> 0.0", NutritionEngine.calculate_bmi(70, 0), 0.0),
]
for name, got, want in extra:
    ok = got == want
    rows.append(dict(profile="unit", age="", sex="", height_cm="", weight_kg="", activity="", goal="",
                     quantity=name, hand_computed=want, engine=got, abs_diff="", pass_=ok, note="unit check"))
    if not ok:
        failures.append(("unit", name, want, got))

OUT.mkdir(parents=True, exist_ok=True)
with open(OUT / "S6_energy_engine.csv", "w", newline="") as fh:
    wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
    wr.writeheader()
    wr.writerows(rows)
summary = {"n_checks": len(rows), "n_pass": sum(r["pass_"] for r in rows), "failures": failures,
           "tolerance_abs": TOL}
(OUT / "S6_energy_engine_summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
