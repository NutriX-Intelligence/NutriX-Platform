import sys
import os
import logging
import pandas as pd
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.db import SessionLocal
from shared.models import Food, FoodNutrient, FoodAlias

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seeders.foods")

def seed_foods():
    logger.info("Starting master foods and aliases seeding...")
    db = SessionLocal()
    try:
        # 1. Read Excel files
        foods_df = pd.read_excel('dataset/ms3_datasets/wholeFoods.xlsx')
        aliases_df = pd.read_excel('dataset/ms3_datasets/foodAliases.xlsx')
        
        foods_df = foods_df.fillna(0.0)

        # 2. Seed Foods and Nutrients
        count = 0
        canonical_map = {} # canonical_name -> food_id
        
        for idx, row in foods_df.iterrows():
            canonical_name = str(row['food_name']).strip()
            code = f"FOOD_{canonical_name.replace(' ', '_').replace('-', '').upper()}"
            
            # Check if exists
            food = db.query(Food).filter(Food.food_code == code).first()
            if not food:
                food = db.query(Food).filter(Food.name.ilike(canonical_name)).first()
                
            if not food:
                food = Food(food_code=code, name=canonical_name.title(), brand="Whole Food")
                db.add(food)
                db.flush()
                count += 1
                
            # Upsert Nutrients
            nutrients = db.query(FoodNutrient).filter(FoodNutrient.food_id == food.id).first()
            if not nutrients:
                nutrients = FoodNutrient(food_id=food.id)
                db.add(nutrients)
                
            nutrients.energy_kcal = float(row['energy_kcal'])
            nutrients.protein_g = float(row['protein_g'])
            nutrients.carb_g = float(row['carb_g'])
            nutrients.fat_g = float(row['fat_g'])
            nutrients.fibre_g = float(row['fibre_g'])
            nutrients.sodium_mg = float(row.get('sodium_mg', 0.0))
            nutrients.sugar_g = float(row.get('sugar_g', 0.0))
            nutrients.saturated_fat_g = float(row.get('saturated_fat_g', 0.0))
            nutrients.calcium_mg = float(row.get('calcium_mg', 0.0))
            nutrients.iron_mg = float(row.get('iron_mg', 0.0))
            nutrients.vitc_mg = float(row.get('vitc_mg', 0.0))
            nutrients.folate_ug = float(row.get('folate_ug', 0.0))
            
            db.flush()
            canonical_map[canonical_name.lower()] = food.id
            
        logger.info(f"Seeded/Verified {count} canonical foods from Excel.")
        db.commit()

        # 3. Seed Aliases
        alias_count = 0
        for idx, row in aliases_df.iterrows():
            canonical_name = str(row['canonical_name']).strip().lower()
            alias_name = str(row['alias_name']).strip()
            language = str(row.get('language', 'en')).strip()
            
            food_id = canonical_map.get(canonical_name)
            if not food_id:
                # Try fetching from DB if not in map
                food = db.query(Food).filter(Food.name.ilike(canonical_name)).first()
                if food:
                    food_id = food.id
                    canonical_map[canonical_name] = food_id
            
            if food_id:
                existing_alias = db.query(FoodAlias).filter(FoodAlias.food_id == food_id, FoodAlias.alias_name == alias_name).first()
                if not existing_alias:
                    new_alias = FoodAlias(food_id=food_id, alias_name=alias_name, language=language)
                    db.add(new_alias)
                    alias_count += 1
            else:
                logger.warning(f"Could not find canonical food '{canonical_name}' for alias '{alias_name}'")
                
        db.commit()
        logger.info(f"Seeded {alias_count} new aliases from Excel.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    seed_foods()
