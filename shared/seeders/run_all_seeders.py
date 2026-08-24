import time
import logging
from shared.seeders.seed_foods import seed_foods
from shared.seeders.seed_recipes import seed_recipes
from shared.seeders.seed_aliases import seed_aliases
from shared.seeders.seed_portions import seed_portions
from shared.seeders.seed_rules import seed_rules
from shared.seeders.seed_prompts import seed_prompts

logger = logging.getLogger("seeders.orchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def run_all():
    start_time = time.time()
    logger.info("=== Starting NutriX Database Seeding Pipeline ===")

    seeders = [
        ("Foods & Nutrients", seed_foods),
        ("Recipes & Ingredients", seed_recipes),
        ("Food Aliases & Synonyms", seed_aliases),
        ("Portions & Unit Conversions", seed_portions),
        ("Dietary Rules & Homely Meals", seed_rules),
        ("System Prompts Registry", seed_prompts)
    ]

    for name, func in seeders:
        s_start = time.time()
        logger.info(f"--> Running seeder: {name}")
        try:
            func()
            logger.info(f"[OK] Completed {name} in {time.time() - s_start:.2f}s")
        except Exception as e:
            logger.error(f"[FAILED] Seeder {name} encountered error: {e}", exc_info=True)
            raise

    logger.info(f"=== Database Seeding Completed Successfully in {time.time() - start_time:.2f}s ===")

if __name__ == "__main__":
    run_all()
