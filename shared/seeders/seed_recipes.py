import os
import re
import ast
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from shared.db import SessionLocal

logger = logging.getLogger("seeders.recipes")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "ms3_user" / "NutriX-main" / "NutriX-main" / "Dataset"
if not RAW_DIR.exists():
    RAW_DIR = BASE_DIR / "dataset"

def categorize_recipe(name):
    name_lower = str(name).lower()
    breakfast_kws = [
        "sandwich", "toast", "pancake", "egg", "omelet", "paratha", "poha", "upma", 
        "idli", "dosa", "oats", "porridge", "muesli", "cereal", "dalia", "flakes",
        "bhurji", "thepla", "cheela", "chilla", "puri", "poori", "chapati", "parotta",
        "appe", "dhokla", "khandvi", "uttapam"
    ]
    if any(kw in name_lower for kw in breakfast_kws):
        if any(kw in name_lower for kw in ["curry", "gravy", "korma"]):
            return "Lunch/Dinner"
        return "Breakfast"
        
    snack_kws = [
        "tea", "coffee", "juice", "shake", "drink", "lassi", "smoothie", "sharbat", 
        "beverage", "soda", "punch", "lemonade", "biscuit", "cookie", "cake", "muffin", 
        "souffle", "pudding", "kheer", "halwa", "laddu", "sweet", "burfi", "chutney", 
        "pickle", "sauce", "dip", "raita", "chips", "popcorn", "samosa", "pakora", 
        "fritter", "chaat", "bhel", "kachori", "salad", "soup", "roll", "cutlet", 
        "snack", "papad", "fry", "bhajia", "vada", "bonda", "kozhukattai", "murukku", 
        "mathri", "namkeen", "shakarpara", "chikki", "pedha", "rasgulla", "gulab jamun",
        "jalebi", "ice cream", "custard", "compote", "sherbet", "jam", "jelly",
        "cooler", "cocoa", "stock", "water", "infusion", "puff"
    ]
    if any(kw in name_lower for kw in snack_kws):
        return "Snack"
        
    return "Lunch/Dinner"

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

def seed_recipes():
    logger.info(f"Starting recipe dataset seeding from: {RAW_DIR}")
    db = SessionLocal()
    try:
        # 1. Base recipe datasets: recipes_names.xlsx, recipes_servingsize.xlsx, INDB.xlsx, recipes.xlsx
        names_file = RAW_DIR / "recipes_names.xlsx"
        servings_file = RAW_DIR / "recipes_servingsize.xlsx"
        indb_file = RAW_DIR / "INDB.xlsx"
        recipes_file = RAW_DIR / "recipes.xlsx"
        recipe_code_map = {}

        if names_file.exists():
            logger.info("Loading recipes_names.xlsx...")
            names_df = pd.read_excel(names_file)
            for idx, row in names_df.iterrows():
                if pd.isna(row.get('recipe_code')) or pd.isna(row.get('recipe_name')):
                    continue
                code = str(row['recipe_code']).strip()
                name = str(row['recipe_name']).strip()
                cat = categorize_recipe(name)
                src = str(row.get('primarysource', 'recipes_names.xlsx')).strip() if pd.notna(row.get('primarysource')) else 'recipes_names.xlsx'

                res = db.execute(
                    text("""
                        INSERT INTO recipes (recipe_code, recipe_name, category, cuisine, difficulty, cooking_time_minutes, instructions, primarysource)
                        VALUES (:code, :name, :cat, 'Indian', 'Medium', 30, 'Follow standard preparation.', :src)
                        ON CONFLICT (recipe_code) DO UPDATE SET recipe_name = EXCLUDED.recipe_name
                        RETURNING id;
                    """),
                    {"code": code, "name": name, "cat": cat, "src": src}
                ).fetchone()

                if res:
                    recipe_code_map[code] = res[0]
            db.commit()
            logger.info(f"Seeded {len(recipe_code_map)} base recipes from recipes_names.xlsx.")

        if servings_file.exists():
            logger.info("Loading recipes_servingsize.xlsx...")
            servings_df = pd.read_excel(servings_file).drop_duplicates(subset=['recipe_code'])
            for idx, row in servings_df.iterrows():
                if pd.isna(row.get('recipe_code')):
                    continue
                code = str(row['recipe_code']).strip()
                no_serv = clean_nutrient_value(row.get('no_of_servings'))
                size_serv = clean_nutrient_value(row.get('size_of_servings'))
                serv_unit = str(row.get('servings_unit', 'serving')).strip() if pd.notna(row.get('servings_unit')) else 'serving'

                db.execute(
                    text("""
                        INSERT INTO servings (recipe_code, no_of_servings, size_of_servings, servings_unit)
                        VALUES (:code, :no_serv, :size_serv, :unit)
                        ON CONFLICT (recipe_code) DO NOTHING;
                    """),
                    {"code": code, "no_serv": no_serv, "size_serv": size_serv, "unit": serv_unit}
                )
            db.commit()
            logger.info("Seeded servings from recipes_servingsize.xlsx.")

        if indb_file.exists():
            logger.info("Loading INDB.xlsx for recipe nutrition...")
            indb_df = pd.read_excel(indb_file)
            for idx, row in indb_df.iterrows():
                if pd.isna(row.get('food_code')):
                    continue
                code = str(row['food_code']).strip()
                recipe_id = recipe_code_map.get(code)
                if not recipe_id:
                    continue

                db.execute(
                    text("""
                        INSERT INTO recipe_nutrition (
                            recipe_id, recipe_code, energy_kcal, carb_g, protein_g, fat_g, freesugar_g, fibre_g,
                            sodium_mg, calcium_mg, iron_mg, vitc_mg, folate_ug,
                            unit_serving_energy_kcal, unit_serving_carb_g, unit_serving_protein_g, unit_serving_fat_g,
                            unit_serving_freesugar_g, unit_serving_fibre_g, unit_serving_sodium_mg, unit_serving_calcium_mg,
                            unit_serving_iron_mg, unit_serving_vitc_mg, unit_serving_folate_ug
                        ) VALUES (
                            :rid, :code, :energy, :carb, :prot, :fat, :sug, :fib,
                            :sod, :calc, :iron, :vitc, :folate,
                            :u_energy, :u_carb, :u_prot, :u_fat, :u_sug, :u_fib,
                            :u_sod, :u_calc, :u_iron, :u_vitc, :u_folate
                        ) ON CONFLICT (recipe_code) DO NOTHING;
                    """),
                    {
                        "rid": recipe_id, "code": code,
                        "energy": clean_nutrient_value(row.get('energy_kcal')),
                        "carb": clean_nutrient_value(row.get('carb_g')),
                        "prot": clean_nutrient_value(row.get('protein_g')),
                        "fat": clean_nutrient_value(row.get('fat_g')),
                        "sug": clean_nutrient_value(row.get('freesugar_g')),
                        "fib": clean_nutrient_value(row.get('fibre_g')),
                        "sod": clean_nutrient_value(row.get('sodium_mg')),
                        "calc": clean_nutrient_value(row.get('calcium_mg')),
                        "iron": clean_nutrient_value(row.get('iron_mg')),
                        "vitc": clean_nutrient_value(row.get('vitc_mg')),
                        "folate": clean_nutrient_value(row.get('folate_ug')),
                        "u_energy": clean_nutrient_value(row.get('unit_serving_energy_kcal')),
                        "u_carb": clean_nutrient_value(row.get('unit_serving_carb_g')),
                        "u_prot": clean_nutrient_value(row.get('unit_serving_protein_g')),
                        "u_fat": clean_nutrient_value(row.get('unit_serving_fat_g')),
                        "u_sug": clean_nutrient_value(row.get('unit_serving_freesugar_g')),
                        "u_fib": clean_nutrient_value(row.get('unit_serving_fibre_g')),
                        "u_sod": clean_nutrient_value(row.get('unit_serving_sodium_mg')),
                        "u_calc": clean_nutrient_value(row.get('unit_serving_calcium_mg')),
                        "u_iron": clean_nutrient_value(row.get('unit_serving_iron_mg')),
                        "u_vitc": clean_nutrient_value(row.get('unit_serving_vitc_mg')),
                        "u_folate": clean_nutrient_value(row.get('unit_serving_folate_ug'))
                    }
                )
            db.commit()
            logger.info("Seeded recipe nutrition from INDB.xlsx.")

        if recipes_file.exists():
            logger.info("Loading recipes.xlsx for recipe ingredients...")
            recipe_ings_df = pd.read_excel(recipes_file)
            for idx, row in recipe_ings_df.iterrows():
                if pd.isna(row.get('recipe_code')):
                    continue
                code = str(row['recipe_code']).strip()
                recipe_id = recipe_code_map.get(code)
                if not recipe_id:
                    continue
                amt = float(row['amount']) if pd.notna(row.get('amount')) else None
                db.execute(
                    text("""
                        INSERT INTO recipe_ingredients (recipe_id, recipe_code, ingredient_name, food_code, food_name, amount, unit, amount_org, unit_org)
                        VALUES (:rid, :code, :ing_name, :fcode, :fname, :amt, :unit, :amt_org, :unit_org);
                    """),
                    {
                        "rid": recipe_id, "code": code,
                        "ing_name": str(row.get('ingredient_name_org', '')).strip() if pd.notna(row.get('ingredient_name_org')) else str(row.get('ingredient_name', '')).strip(),
                        "fcode": str(row.get('food_code', '')).strip() if pd.notna(row.get('food_code')) else None,
                        "fname": str(row.get('food_name', '')).strip() if pd.notna(row.get('food_name')) else None,
                        "amt": amt,
                        "unit": str(row.get('unit', '')).strip() if pd.notna(row.get('unit')) else None,
                        "amt_org": str(row.get('amount_org', '')) if pd.notna(row.get('amount_org')) else None,
                        "unit_org": str(row.get('unit_org', '')) if pd.notna(row.get('unit_org')) else None
                    }
                )
            db.commit()
            logger.info("Seeded recipe ingredients from recipes.xlsx.")

        # 2. Regional Cuisines (10 CSVs)
        regional_files = [
            ("bengali_foods.csv", "Bengali", "REG_BENGALI"),
            ("chinese_foods.csv", "Chinese", "REG_CHINESE"),
            ("gujarati_kathiyawadi_foods.csv", "Gujarati", "REG_GUJARATI"),
            ("italian_foods.csv", "Italian", "REG_ITALIAN"),
            ("japanese_foods.csv", "Japanese", "REG_JAPANESE"),
            ("maharashtrian_foods.csv", "Maharashtrian", "REG_MAHARASHTRIAN"),
            ("mexican_foods.csv", "Mexican", "REG_MEXICAN"),
            ("punjabi_foods.csv", "Punjabi", "REG_PUNJABI"),
            ("rajasthani_foods.csv", "Rajasthani", "REG_RAJASTHANI"),
            ("south_indian_foods.csv", "South Indian", "REG_SOUTH_INDIAN"),
        ]

        reg_total = 0
        for filename, cuisine_name, prefix in regional_files:
            filepath = RAW_DIR / filename
            if not filepath.exists():
                continue
            df = pd.read_csv(filepath, encoding="utf-8", on_bad_lines='skip')
            for idx, row in df.iterrows():
                dish_name = str(row.get('Dish Name', '')).strip()
                if not dish_name:
                    continue
                code = f"{prefix}_{idx:04d}"
                cat = categorize_recipe(dish_name)
                instructions = str(row.get('Recipe Instructions', 'Follow standard recipe preparation.')).strip()

                res = db.execute(
                    text("""
                        INSERT INTO recipes (recipe_code, recipe_name, category, cuisine, difficulty, cooking_time_minutes, instructions, primarysource)
                        VALUES (:code, :name, :cat, :cuisine, 'Medium', 30, :inst, :src)
                        ON CONFLICT (recipe_code) DO NOTHING
                        RETURNING id;
                    """),
                    {"code": code, "name": dish_name, "cat": cat, "cuisine": cuisine_name, "inst": instructions, "src": filename}
                ).fetchone()

                if res:
                    recipe_id = res[0]
                    cal_str = str(row.get('Calories (per serving)', ''))
                    nut_str = str(row.get('Key Nutrients', ''))
                    cal_m = re.search(r'(\d+)', cal_str)
                    energy_kcal = float(cal_m.group(1)) if cal_m else 250.0

                    p_m = re.search(r'Protein\s*\(([\d\.]+)g\)', nut_str, re.I)
                    f_m = re.search(r'Fat\s*\(([\d\.]+)g\)', nut_str, re.I)
                    c_m = re.search(r'Carbohydrates\s*\(([\d\.]+)g\)', nut_str, re.I)
                    fib_m = re.search(r'Fiber\s*\(([\d\.]+)g\)', nut_str, re.I)

                    prot = float(p_m.group(1)) if p_m else 8.0
                    fat = float(f_m.group(1)) if f_m else 10.0
                    carb = float(c_m.group(1)) if c_m else 35.0
                    fib = float(fib_m.group(1)) if fib_m else 3.0

                    db.execute(
                        text("""
                            INSERT INTO recipe_nutrition (
                                recipe_id, recipe_code, energy_kcal, carb_g, protein_g, fat_g, freesugar_g, fibre_g, sodium_mg, calcium_mg, iron_mg, vitc_mg, folate_ug,
                                unit_serving_energy_kcal, unit_serving_carb_g, unit_serving_protein_g, unit_serving_fat_g, unit_serving_freesugar_g, unit_serving_fibre_g,
                                unit_serving_sodium_mg, unit_serving_calcium_mg, unit_serving_iron_mg, unit_serving_vitc_mg, unit_serving_folate_ug
                            ) VALUES (
                                :rid, :code, :energy, :carb, :prot, :fat, 0.0, :fib, 300.0, 50.0, 2.0, 5.0, 20.0,
                                :energy, :carb, :prot, :fat, 0.0, :fib, 300.0, 50.0, 2.0, 5.0, 20.0
                            ) ON CONFLICT (recipe_code) DO NOTHING;
                        """),
                        {"rid": recipe_id, "code": code, "energy": energy_kcal, "carb": carb, "prot": prot, "fat": fat, "fib": fib}
                    )

                    ings_str = str(row.get('Ingredients Required', ''))
                    if ings_str:
                        for ing_name in [i.strip() for i in ings_str.split(',') if i.strip()]:
                            db.execute(
                                text("""
                                    INSERT INTO recipe_ingredients (recipe_id, recipe_code, ingredient_name, food_name, amount, unit)
                                    VALUES (:rid, :code, :ing, :ing, 1.0, 'portion');
                                """),
                                {"rid": recipe_id, "code": code, "ing": ing_name}
                            )

                    db.execute(
                        text("""
                            INSERT INTO servings (recipe_code, no_of_servings, size_of_servings, servings_unit)
                            VALUES (:code, 1.0, 1.0, 'serving')
                            ON CONFLICT (recipe_code) DO NOTHING;
                        """),
                        {"code": code}
                    )
                    reg_total += 1
            db.commit()
        logger.info(f"Seeded {reg_total} recipes from Regional cuisine files.")

        logger.info("Recipe seeding completed successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error during recipe seeding: {e}", exc_info=True)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_recipes()
