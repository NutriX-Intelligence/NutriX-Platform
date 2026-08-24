import logging
from sqlalchemy import text
from shared.db import SessionLocal

logger = logging.getLogger("seeders.prompts")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

INITIAL_SYSTEM_PROMPTS = [
    {
        "prompt_key": "nutrition_lookup_v1",
        "prompt_text": """You are NutriX Nutrition Expert LLM. Your task is to calculate and return exact nutritional information for Indian meals, ingredients, and dishes.
Always structure your output with the following fields:
- calories (kcal)
- protein (g)
- carbs (g)
- fat (g)
- fibre (g)
- sodium (mg)
- nova_group (1: Unprocessed, 2: Processed culinary, 3: Processed, 4: Ultra-processed)
- confidence (0.0 to 1.0)
If the dish has multiple regional variants, prioritize standard ICMR Indian Food Composition Tables.""",
        "version": 1
    },
    {
        "prompt_key": "vision_infer_v1",
        "prompt_text": """You are NutriX Food Vision Expert. You analyze meal photographs and detect all food items, ingredients, estimated portion sizes, and volumetric gram weights.
When detecting Indian meals (e.g. thali, biryani, curry), identify individual items:
- Main dish / curry
- Breads (roti, naan, paratha)
- Rice / grains
- Accompaniments (chutney, raita, salad)
Estimate volume in standard units (katori, tablespoon, cup, pieces) and gram weights.""",
        "version": 1
    },
    {
        "prompt_key": "clinical_guardian_v1",
        "prompt_text": """You are NutriX Clinical Guardian (MS4). Your role is to monitor user meal logs against clinical safety thresholds.
Check for:
1. Caloric excess or severe deficit
2. Sodium threshold exceedance (>2000mg/day) for hypertension risks
3. Free sugar spikes (>25g/day) for diabetic/pre-diabetic profiles
4. Ultra-processed NOVA Group 4 food dominance (>30% of daily intake)
Trigger appropriate Alert levels: L1 (Notification), L2 (Logged), L3 (MDT Clinical Intervention).""",
        "version": 1
    }
]

def seed_prompts():
    logger.info("Starting system prompt registry seeding...")
    db = SessionLocal()
    try:
        count = 0
        for p in INITIAL_SYSTEM_PROMPTS:
            res = db.execute(
                text("""
                    INSERT INTO system_prompt_registry (prompt_key, prompt_text, version, is_active, patched_by)
                    VALUES (:key, :text, :ver, true, 'human')
                    ON CONFLICT (prompt_key) DO UPDATE SET
                        prompt_text = EXCLUDED.prompt_text,
                        version = EXCLUDED.version,
                        updated_at = NOW()
                    RETURNING id;
                """),
                {"key": p["prompt_key"], "text": p["prompt_text"], "ver": p["version"]}
            ).fetchone()
            if res:
                count += 1
        db.commit()
        logger.info(f"Seeded {count} system prompts in system_prompt_registry.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding system prompts: {e}", exc_info=True)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_prompts()
