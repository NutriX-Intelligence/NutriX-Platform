import os
import re
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from shared.db import SessionLocal

logger = logging.getLogger("seeders.foods")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "ms3_user" / "NutriX-main" / "NutriX-main" / "Dataset"
if not RAW_DIR.exists():
    RAW_DIR = BASE_DIR / "dataset"

def clean_nutrient_value(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    if val_str.lower() in ('tr', 'trace'):
        return 0.01
    if val_str.lower() in ('n', 'n/a', 'none', '', 'null'):
        return 0.0
    try:
        cleaned = re.sub(r'[^\d\.\-]', '', val_str)
        if not cleaned:
            return 0.0
        return float(cleaned)
    except Exception:
        return 0.0

def seed_foods():
    logger.info(f"Starting food dataset seeding from: {RAW_DIR}")
    db = SessionLocal()
    try:
        # 1. Indian Food DF packaged dataset
        pkg_file = RAW_DIR / "Indian_Food_DF.csv"
        if pkg_file.exists():
            logger.info("Loading Indian_Food_DF.csv...")
            food_df = pd.read_csv(pkg_file, encoding="utf-8", on_bad_lines='skip')
            pkg_count = 0
            for idx, row in food_df.iterrows():
                name = row.get('name')
                if not name or pd.isna(name):
                    continue
                brand = row.get('brand')
                brand_val = str(brand).strip() if pd.notna(brand) else None
                fcode = f"PACKAGED_{idx:04d}"

                # Insert food
                res = db.execute(
                    text("""
                        INSERT INTO foods (food_code, name, brand)
                        VALUES (:code, :name, :brand)
                        ON CONFLICT (food_code) DO NOTHING
                        RETURNING id;
                    """),
                    {"code": fcode, "name": str(name).strip(), "brand": brand_val}
                ).fetchone()

                if res:
                    food_id = res[0]
                    salt = clean_nutrient_value(row.get('nutri_salt'))
                    sodium = salt * 400.0
                    energy_kcal = clean_nutrient_value(row.get('nutri_energy'))
                    protein_g = clean_nutrient_value(row.get('nutri_protein'))
                    carb_g = clean_nutrient_value(row.get('nutri_carbohydrate'))
                    fat_g = clean_nutrient_value(row.get('nutri_fat'))
                    fibre_g = clean_nutrient_value(row.get('nutri_fiber'))
                    sugar_g = clean_nutrient_value(row.get('nutri_sugar'))
                    saturated_fat_g = clean_nutrient_value(row.get('nutri_satuFat'))

                    db.execute(
                        text("""
                            INSERT INTO food_nutrients (
                                food_id, energy_kcal, protein_g, carb_g, fat_g, fibre_g, sodium_mg, sugar_g, saturated_fat_g
                            ) VALUES (
                                :food_id, :energy, :prot, :carb, :fat, :fib, :sod, :sug, :sat_fat
                            ) ON CONFLICT (food_id) DO NOTHING;
                        """),
                        {
                            "food_id": food_id,
                            "energy": energy_kcal,
                            "prot": protein_g,
                            "carb": carb_g,
                            "fat": fat_g,
                            "fib": fibre_g,
                            "sod": sodium,
                            "sug": sugar_g,
                            "sat_fat": saturated_fat_g
                        }
                    )
                    pkg_count += 1
            db.commit()
            logger.info(f"Seeded {pkg_count} foods from Indian_Food_DF.csv.")

        # 2. UK FCT
        uk_file = RAW_DIR / "UK_fct.xlsx"
        if uk_file.exists():
            logger.info("Loading UK_fct.xlsx...")
            uk_df = pd.read_excel(uk_file, sheet_name="Sheet1")
            uk_count = 0
            for idx, row in uk_df.iterrows():
                fcode = row.get('food_code')
                fname = row.get('food_name')
                if not fname or pd.isna(fname) or not fcode or pd.isna(fcode):
                    continue
                code_val = f"UKFCT_{str(fcode).strip()}"

                res = db.execute(
                    text("""
                        INSERT INTO foods (food_code, name)
                        VALUES (:code, :name)
                        ON CONFLICT (food_code) DO NOTHING
                        RETURNING id;
                    """),
                    {"code": code_val, "name": str(fname).strip()}
                ).fetchone()

                if res:
                    food_id = res[0]
                    db.execute(
                        text("""
                            INSERT INTO food_nutrients (
                                food_id, energy_kcal, protein_g, carb_g, fat_g, fibre_g, sodium_mg, sugar_g, saturated_fat_g, calcium_mg, iron_mg, vitc_mg, folate_ug
                            ) VALUES (
                                :food_id, :energy, :prot, :carb, :fat, :fib, :sod, :sug, :sat_fat, :calc, :iron, :vitc, :folate
                            ) ON CONFLICT (food_id) DO NOTHING;
                        """),
                        {
                            "food_id": food_id,
                            "energy": clean_nutrient_value(row.get('energy_kcal')),
                            "prot": clean_nutrient_value(row.get('protein_g')),
                            "carb": clean_nutrient_value(row.get('carb_g')),
                            "fat": clean_nutrient_value(row.get('fat_g')),
                            "fib": clean_nutrient_value(row.get('fibre_g')),
                            "sod": clean_nutrient_value(row.get('sodium_mg')),
                            "sug": clean_nutrient_value(row.get('freesugar_g')),
                            "sat_fat": clean_nutrient_value(row.get('sfa_mg')) / 1000.0,
                            "calc": clean_nutrient_value(row.get('calcium_mg')),
                            "iron": clean_nutrient_value(row.get('iron_mg')),
                            "vitc": clean_nutrient_value(row.get('vitc_mg')),
                            "folate": clean_nutrient_value(row.get('folate_ug'))
                        }
                    )
                    uk_count += 1
            db.commit()
            logger.info(f"Seeded {uk_count} foods from UK_fct.xlsx.")

        # 3. US FCT
        us_file = RAW_DIR / "US_fct.xlsx"
        if us_file.exists():
            logger.info("Loading US_fct.xlsx...")
            us_df = pd.read_excel(us_file, sheet_name="Sheet1")
            us_count = 0
            for idx, row in us_df.iterrows():
                fcode = row.get('food_code')
                fname = row.get('food_name')
                if not fname or pd.isna(fname) or not fcode or pd.isna(fcode):
                    continue
                code_val = f"USFCT_{str(fcode).strip()}"

                res = db.execute(
                    text("""
                        INSERT INTO foods (food_code, name)
                        VALUES (:code, :name)
                        ON CONFLICT (food_code) DO NOTHING
                        RETURNING id;
                    """),
                    {"code": code_val, "name": str(fname).strip()}
                ).fetchone()

                if res:
                    food_id = res[0]
                    db.execute(
                        text("""
                            INSERT INTO food_nutrients (
                                food_id, energy_kcal, protein_g, carb_g, fat_g, fibre_g, sodium_mg, sugar_g, saturated_fat_g, calcium_mg, iron_mg, vitc_mg, folate_ug
                            ) VALUES (
                                :food_id, :energy, :prot, :carb, :fat, :fib, :sod, :sug, :sat_fat, :calc, :iron, :vitc, :folate
                            ) ON CONFLICT (food_id) DO NOTHING;
                        """),
                        {
                            "food_id": food_id,
                            "energy": clean_nutrient_value(row.get('energy_kcal')),
                            "prot": clean_nutrient_value(row.get('protein_g')),
                            "carb": clean_nutrient_value(row.get('carb_g')),
                            "fat": clean_nutrient_value(row.get('fat_g')),
                            "fib": clean_nutrient_value(row.get('fibre_g')),
                            "sod": clean_nutrient_value(row.get('sodium_mg')),
                            "sug": clean_nutrient_value(row.get('freesugar_g')),
                            "sat_fat": clean_nutrient_value(row.get('sfa_mg')) / 1000.0,
                            "calc": clean_nutrient_value(row.get('calcium_mg')),
                            "iron": clean_nutrient_value(row.get('iron_mg')),
                            "vitc": clean_nutrient_value(row.get('vitc_mg')),
                            "folate": clean_nutrient_value(row.get('folate_ug'))
                        }
                    )
                    us_count += 1
            db.commit()
            logger.info(f"Seeded {us_count} foods from US_fct.xlsx.")

        # 4. Indian Food Nutrition Dataset CSV
        ind_csv = RAW_DIR / "indian_food_nutrition_dataset.csv"
        if ind_csv.exists():
            logger.info("Loading indian_food_nutrition_dataset.csv...")
            ind_count = 0
            with open(ind_csv, "r", encoding="utf-8") as f:
                f.readline()
                for idx, line in enumerate(f):
                    parts = line.strip().split(',')
                    if len(parts) < 8:
                        continue
                    name = ",".join(parts[:-7]).strip()
                    category = parts[-7].strip()
                    calories = clean_nutrient_value(parts[-5])
                    protein = clean_nutrient_value(parts[-4])
                    carbs = clean_nutrient_value(parts[-3])
                    fats = clean_nutrient_value(parts[-2])
                    dietary_pref = parts[-1].strip()

                    code_val = f"IND_FOOD_{idx:04d}"
                    res = db.execute(
                        text("""
                            INSERT INTO foods (food_code, name)
                            VALUES (:code, :name)
                            ON CONFLICT (food_code) DO NOTHING
                            RETURNING id;
                        """),
                        {"code": code_val, "name": name}
                    ).fetchone()

                    if res:
                        food_id = res[0]
                        db.execute(
                            text("""
                                INSERT INTO food_nutrients (
                                    food_id, energy_kcal, protein_g, carb_g, fat_g
                                ) VALUES (
                                    :food_id, :energy, :prot, :carb, :fat
                                ) ON CONFLICT (food_id) DO NOTHING;
                            """),
                            {"food_id": food_id, "energy": calories, "prot": protein, "carb": carbs, "fat": fats}
                        )
                        ind_count += 1
            db.commit()
            logger.info(f"Seeded {ind_count} foods from indian_food_nutrition_dataset.csv.")

        logger.info("Food seeding completed successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error during food seeding: {e}", exc_info=True)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_foods()
