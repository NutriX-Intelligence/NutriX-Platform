import re
import logging
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from shared.db import SessionLocal

logger = logging.getLogger("seeders.portions")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "ms3_user" / "NutriX-main" / "NutriX-main" / "Dataset"
if not RAW_DIR.exists():
    RAW_DIR = BASE_DIR / "dataset"

def parse_gram_weight(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip().lower()
    val_str = val_str.replace('1/4', '0.25').replace('1/2', '0.5').replace('3/4', '0.75').replace('1/3', '0.33')
    match = re.match(r'^([\d\.]+)\s*(?:g|ml)$', val_str)
    if match:
        return float(match.group(1))
    coeff_match = re.search(r'([\d\.]+)', val_str)
    if coeff_match:
        coeff = float(coeff_match.group(1))
        unit_word = re.sub(r'[\d\.\s]', '', val_str)
        if 'tsp' in unit_word or 'teaspoon' in unit_word:
            return coeff * 5.0
        elif 'tbsp' in unit_word or 'tablespoon' in unit_word:
            return coeff * 15.0
        elif 'cup' in unit_word or unit_word == 'c':
            return coeff * 240.0
        elif 'glass' in unit_word:
            return coeff * 200.0
        elif 'bowl' in unit_word or 'katori' in unit_word:
            return coeff * 150.0
        elif 'piece' in unit_word or 'pcs' in unit_word or 'pc' in unit_word:
            return coeff * 50.0
        elif 'knob' in unit_word:
            return coeff * 20.0
        elif 'blob' in unit_word:
            return coeff * 15.0
        elif 'slice' in unit_word:
            return coeff * 25.0
        elif 'drop' in unit_word:
            return coeff * 0.05
        elif 'sprig' in unit_word:
            return coeff * 1.0
        elif 'strand' in unit_word:
            return coeff * 0.01
        elif 'leaf' in unit_word or 'leaves' in unit_word:
            return coeff * 0.1
        elif 'no' in unit_word or 'number' in unit_word:
            return coeff * 1.0
        if not unit_word:
            return coeff
    return None

def seed_portions():
    logger.info("Starting unit conversions and food portions seeding...")
    db = SessionLocal()
    try:
        units_file = RAW_DIR / "Units.xlsx"
        units_count = 0
        if units_file.exists():
            logger.info("Loading Units.xlsx...")
            units_df = pd.read_excel(units_file)
            units_df['Food items'] = units_df['Food items'].ffill()

            for idx, row in units_df.iterrows():
                food_item = row.get('Food items')
                unit = row.get('Units')
                units_1_val = row.get('Units.1')
                
                if pd.isna(food_item) or (pd.isna(unit) and pd.isna(units_1_val)):
                    continue
                    
                gram_weight = parse_gram_weight(units_1_val)
                if gram_weight is None:
                    gram_weight = parse_gram_weight(unit)
                if gram_weight is None:
                    continue
                    
                unit_str = str(unit).strip() if pd.notna(unit) else "piece"
                source_val = str(row.get('Source')).strip() if pd.notna(row.get('Source')) else "Units.xlsx"
                
                db.execute(
                    text("""
                        INSERT INTO unit_conversions (food_item, unit, gram_weight, source)
                        VALUES (:item, :unit, :gw, :src);
                    """),
                    {"item": str(food_item).strip(), "unit": unit_str, "gw": float(gram_weight), "src": source_val}
                )
                units_count += 1
            db.commit()
            logger.info(f"Seeded {units_count} unit conversions from Units.xlsx.")

        # Skipping food_portions since it has been removed from database schema
        pass
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding portions: {e}", exc_info=True)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_portions()
