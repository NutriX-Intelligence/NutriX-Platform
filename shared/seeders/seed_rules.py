import logging
from sqlalchemy import text
from shared.db import SessionLocal

logger = logging.getLogger("seeders.rules")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Dietary rules exclusions
RULES = [
    # Jain exclusions (no onion, garlic, ginger, potatoes, root vegetables, eggplant)
    ("onion", "exclude_jain", True),
    ("garlic", "exclude_jain", True),
    ("ginger", "exclude_jain", True),
    ("potato", "exclude_jain", True),
    ("potatoes", "exclude_jain", True),
    ("carrot", "exclude_jain", True),
    ("carrots", "exclude_jain", True),
    ("radish", "exclude_jain", True),
    ("beetroot", "exclude_jain", True),
    ("baingan", "exclude_jain", True),
    ("eggplant", "exclude_jain", True),
    ("aubergine", "exclude_jain", True),
    
    # Vegetarian exclusions (no meat, chicken, mutton, fish, beef, pork, seafood, eggs)
    ("chicken", "exclude_vegetarian", True),
    ("mutton", "exclude_vegetarian", True),
    ("fish", "exclude_vegetarian", True),
    ("beef", "exclude_vegetarian", True),
    ("pork", "exclude_vegetarian", True),
    ("meat", "exclude_vegetarian", True),
    ("prawn", "exclude_vegetarian", True),
    ("shrimp", "exclude_vegetarian", True),
    ("crab", "exclude_vegetarian", True),
    ("lamb", "exclude_vegetarian", True),
    ("egg", "exclude_vegetarian", True),
    ("eggs", "exclude_vegetarian", True),
    
    # Eggetarian allows eggs but no meat
    ("chicken", "exclude_eggetarian", True),
    ("mutton", "exclude_eggetarian", True),
    ("fish", "exclude_eggetarian", True),
    ("beef", "exclude_eggetarian", True),
    ("pork", "exclude_eggetarian", True),
    ("meat", "exclude_eggetarian", True),
    
    # Vegan exclusions (no dairy, honey, eggs, meat)
    ("chicken", "exclude_vegan", True),
    ("mutton", "exclude_vegan", True),
    ("fish", "exclude_vegan", True),
    ("beef", "exclude_vegan", True),
    ("pork", "exclude_vegan", True),
    ("meat", "exclude_vegan", True),
    ("egg", "exclude_vegan", True),
    ("eggs", "exclude_vegan", True),
    ("milk", "exclude_vegan", True),
    ("cheese", "exclude_vegan", True),
    ("butter", "exclude_vegan", True),
    ("curd", "exclude_vegan", True),
    ("yogurt", "exclude_vegan", True),
    ("ghee", "exclude_vegan", True),
    ("paneer", "exclude_vegan", True),
    ("honey", "exclude_vegan", True),
]

POPULAR_HOMELY_MEALS = [
    {
        "name": "Vada pav",
        "cuisine": "Indian",
        "region": "West India",
        "is_community": True,
        "status": "approved",
        "ingredients": [
            {"ingredient_name": "potato", "amount": 1.0, "unit": "piece", "gram_weight": 80.0},
            {"ingredient_name": "bread bun", "amount": 1.0, "unit": "piece", "gram_weight": 60.0},
            {"ingredient_name": "butter", "amount": 1.0, "unit": "tsp", "gram_weight": 5.0},
            {"ingredient_name": "oil", "amount": 1.0, "unit": "tsp", "gram_weight": 5.0}
        ],
        "nutrition": {
            "energy_kcal": 290.0, "protein_g": 6.5, "carb_g": 42.0, "fat_g": 11.0,
            "fibre_g": 3.2, "sodium_mg": 460.0, "sugar_g": 2.5
        }
    },
    {
        "name": "Ghee Rice",
        "cuisine": "Indian",
        "region": "South India",
        "is_community": True,
        "status": "approved",
        "ingredients": [
            {"ingredient_name": "rice", "amount": 1.0, "unit": "cup", "gram_weight": 195.0},
            {"ingredient_name": "ghee", "amount": 2.0, "unit": "tsp", "gram_weight": 10.0}
        ],
        "nutrition": {
            "energy_kcal": 360.0, "protein_g": 6.0, "carb_g": 55.0, "fat_g": 12.0,
            "fibre_g": 1.5, "sodium_mg": 150.0, "sugar_g": 0.2
        }
    },
    {
        "name": "Poha",
        "cuisine": "Indian",
        "region": "Central India",
        "is_community": True,
        "status": "approved",
        "ingredients": [
            {"ingredient_name": "flattened rice", "amount": 1.5, "unit": "cup", "gram_weight": 90.0},
            {"ingredient_name": "onion", "amount": 0.5, "unit": "piece", "gram_weight": 40.0},
            {"ingredient_name": "peanuts", "amount": 1.0, "unit": "tbsp", "gram_weight": 12.0},
            {"ingredient_name": "oil", "amount": 1.0, "unit": "tsp", "gram_weight": 5.0}
        ],
        "nutrition": {
            "energy_kcal": 280.0, "protein_g": 7.0, "carb_g": 40.0, "fat_g": 9.5,
            "fibre_g": 3.5, "sodium_mg": 320.0, "sugar_g": 1.8
        }
    }
]

def seed_rules():
    logger.info("Starting ingredient rules and homely meals seeding...")
    db = SessionLocal()
    try:
        rule_count = 0
        for ing_name, rtype, val in RULES:
            exists = db.execute(
                text("SELECT id FROM ingredient_rules WHERE ingredient_name = :ing AND rule_type = :rtype;"),
                {"ing": ing_name, "rtype": rtype}
            ).fetchone()
            if not exists:
                db.execute(
                    text("INSERT INTO ingredient_rules (ingredient_name, rule_type, value) VALUES (:ing, :rtype, :val);"),
                    {"ing": ing_name, "rtype": rtype, "val": val}
                )
                rule_count += 1
        db.commit()
        logger.info(f"Seeded {rule_count} ingredient rules.")

        # Seed homely meals
        hm_count = 0
        for hm in POPULAR_HOMELY_MEALS:
            exists = db.execute(
                text("SELECT id FROM homely_meals WHERE name = :name;"),
                {"name": hm["name"]}
            ).fetchone()
            if not exists:
                res = db.execute(
                    text("""
                        INSERT INTO homely_meals (name, creator_id, is_community, status, popularity, cuisine, region)
                        VALUES (:name, NULL, :comm, :status, 10, :cuisine, :region)
                        RETURNING id;
                    """),
                    {
                        "name": hm["name"],
                        "comm": hm["is_community"],
                        "status": hm["status"],
                        "cuisine": hm["cuisine"],
                        "region": hm["region"]
                    }
                ).fetchone()
                if res:
                    mid = res[0]
                    nut = hm["nutrition"]
                    db.execute(
                        text("""
                            INSERT INTO homely_meal_nutrition (meal_id, energy_kcal, protein_g, carb_g, fat_g, fibre_g, sodium_mg, sugar_g)
                            VALUES (:mid, :energy, :prot, :carb, :fat, :fib, :sod, :sug);
                        """),
                        {"mid": mid, "energy": nut["energy_kcal"], "prot": nut["protein_g"], "carb": nut["carb_g"], "fat": nut["fat_g"], "fib": nut["fibre_g"], "sod": nut["sodium_mg"], "sug": nut["sugar_g"]}
                    )
                    for ing in hm["ingredients"]:
                        db.execute(
                            text("""
                                INSERT INTO homely_meal_ingredients (meal_id, ingredient_name, amount, unit, gram_weight)
                                VALUES (:mid, :ing, :amt, :unit, :gw);
                            """),
                            {"mid": mid, "ing": ing["ingredient_name"], "amt": ing["amount"], "unit": ing["unit"], "gw": ing["gram_weight"]}
                        )
                    hm_count += 1
        db.commit()
        logger.info(f"Seeded {hm_count} homely meals.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding rules: {e}", exc_info=True)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_rules()
