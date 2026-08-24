import logging
from sqlalchemy import text
from shared.db import SessionLocal

logger = logging.getLogger("seeders.aliases")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Common Indian food aliases mapping English/Common names to regional synonyms
ALIASES_MAPPING = {
    "potato": ["alu", "aloo", "batata", "urulaikizhangu", "bangaladumpa", "alu gadda"],
    "onion": ["pyaz", "pyaaz", "kanda", "vengayam", "ullipayalu", "eerulli"],
    "tomato": ["tamatar", "thakkali", "tamata", "tomato hannu"],
    "ginger": ["adrak", "inji", "allam", "shunti", "aada"],
    "garlic": ["lahsun", "poondu", "vellulli", "bellulli", "roshun"],
    "spinach": ["palak", "pasalai keerai", "palakura", "palak soppu", "palong shaak"],
    "rice": ["chawal", "saadam", "biyyam", "anna", "bhaat"],
    "wheat flour": ["atta", "aata", "godhumai maavu", "godhuma pindi", "godhi hittu"],
    "lentils": ["dal", "daal", "paruppu", "pappu", "bele"],
    "chickpeas": ["chana", "chole", "kondakadalai", "senagalu", "kadale kaalu", "kabuli chana"],
    "kidney beans": ["rajma", "rajmah"],
    "cottage cheese": ["paneer", "panir"],
    "curd": ["dahi", "thayir", "perugu", "mosaru", "doi"],
    "clarified butter": ["ghee", "neyyi", "tuppa", "ghee"],
    "mustard seeds": ["rai", "sarson", "kadugu", "aavalu", "sasive", "shorshe"],
    "cumin seeds": ["jeera", "zeera", "seeragam", "jeelakarra", "jeerige", "jira"],
    "coriander": ["dhania", "kothmir", "kothamalli", "kothimiri", "kothambari"],
    "fenugreek": ["methi", "vendhayam", "menthulu", "menthya"],
    "turmeric": ["haldi", "manjal", "pasupu", "arishina", "holud"],
    "okra": ["bhindi", "bhendi", "vendakkai", "bhendi kayi"],
    "eggplant": ["baingan", "brinjal", "kathirikai", "vankaya", "badanekayi", "begun"],
    "cauliflower": ["gobi", "gobhi", "phool gobi"],
    "cabbage": ["patta gobi", "bandha gobi", "muttakose"]
}

def seed_aliases():
    logger.info("Skipping food aliases seeding: food_aliases table has been removed from the database schema.")

if __name__ == "__main__":
    seed_aliases()
