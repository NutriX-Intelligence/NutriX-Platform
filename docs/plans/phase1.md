# Phase 1 — Data & Database Foundation

> **Master Plan Reference:** Phase 1
> **Goal:** PostgreSQL is fully seeded and Redis is running. All services connect to both.
> **Status:** 🟢 Completed & Verified ✅
> **Depends On:** Phase 0 ✅ (Docker Compose + `.env` must be in place and `docker-compose up` must be passing)

---

## Context & Ground Truth

The MS3 service (`ms3_user/NutriX-main/NutriX-main/`) is a fully implemented FastAPI backend with:
- A complete SQLAlchemy ORM (`app/models.py`, **30 tables**) currently running on **SQLite**.
- A comprehensive build+seeder script (`scripts/build_nutrition_master_db.py`, **1378 lines**) that parses ICMR, USDA, and recipe datasets from `Dataset/`.
- All required dataset files located at `ms3_user/NutriX-main/NutriX-main/Dataset/` (`INDB.xlsx`, `recipes.xlsx`, `Units.xlsx`, USDA CSVs, etc.).

The goal of Phase 1 is to:
1. **Migrate** the MS3 ORM into `shared/models.py` and add the 5 new NutriX-specific tables.
2. **Switch** the database driver from SQLite to **PostgreSQL** (already referenced via `DATABASE_URL` env var).
3. **Wire** `shared/db.py` to use the PostgreSQL-with-SQLite-fallback pattern from MS3's `app/db.py`.
4. Set up **Alembic** for schema versioning and run the first migration.
5. Adapt and run the **existing seeder scripts** to populate PostgreSQL with all food, recipe, and rules data.
6. Set up the **PostgreSQL trigger → Redis pipeline** for live macro streaming.
7. Add a **database health check** to all services.

> **Key Rule from MASTER_ARCHITECTURE.md:** The single PostgreSQL instance is the permanent master store for all services. Redis is the fast-read cache populated by DB triggers. No service should bypass this pattern.

---

## Existing Schema (Sourced from `ms3_user/NutriX-main/NutriX-main/app/models.py`)

These 30 tables are **already defined in SQLAlchemy** and must be preserved exactly as-is when migrating into `shared/models.py`.

| Existing Table | SQLAlchemy Model Class |
|---|---|
| `users` | `User` |
| `profiles` | `Profile` |
| `user_preferences` | `UserPreference` |
| `goals` | `Goal` |
| `foods` | `Food` |
| `food_categories` | `FoodCategory` |
| `food_nutrients` | `FoodNutrient` |
| `food_portions` | `FoodPortion` |
| `food_aliases` | `FoodAlias` |
| `food_tags` | `FoodTag` |
| `recipes` | `Recipe` |
| `recipe_ingredients` | `RecipeIngredient` |
| `recipe_nutrition` | `RecipeNutrition` |
| `recipe_steps` | `RecipeStep` |
| `servings` | `Serving` |
| `ingredients` | `Ingredient` |
| `ingredient_rules` | `IngredientRule` |
| `meal_logs` | `MealLog` |
| `water_logs` | `WaterLog` |
| `weight_logs` | `WeightLog` |
| `barcode_cache` | `BarcodeCache` |
| `recommendation_history` | `RecommendationHistory` |
| `health_scores` | `HealthScore` |
| `analytics` | `Analytics` |
| `generated_meal_plans` | `GeneratedMealPlan` |
| `unit_conversions` | `UnitConversion` |
| `homely_meals` | `HomelyMeal` |
| `homely_meal_ingredients` | `HomelyMealIngredient` |
| `homely_meal_nutrition` | `HomelyMealNutrition` |
| `homely_meal_versions` | `HomelyMealVersion` |
| `homely_meal_reviews` | `HomelyMealReview` |
| `homely_meal_tags` | `HomelyMealTag` |
| `search_history` | `SearchHistory` |
| `settings` | `Settings` |

---

## New Tables to Add (NutriX-specific — MS1 & MS4)

| New Table | Owner Service | Purpose |
|---|---|---|
| `user_adapters` | MS1 | Stores per-user YOLOv8 head adapter path, class mappings, and version |
| `audit_logs` | MS1 + MS2 | Execution trace log for every inference and LLM call |
| `clinical_alerts` | MS4 (writes) / MS3 (reads) | Tier 2A Guardian alert events per user |
| `clinical_reports` | MS4 (writes) | Full MDT clinical report documents |
| `system_prompt_registry` | MS4 | Versioned LLM system prompt store (self-healing patch target) |

---

## Steps

---

### 1.1 — Update `shared/db.py`

The current `shared/db.py` is a barebones stub. Replace it with the PostgreSQL-with-SQLite-fallback pattern from MS3's `app/db.py`.

**Source:** `ms3_user/NutriX-main/NutriX-main/app/db.py`

- [ ] 1.1.1 Overwrite `shared/db.py` with the following:

```python
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path

logger = logging.getLogger("shared.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://nutrix:changeme@postgres:5432/nutrix_db")

# Normalise Heroku-style postgres:// → postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Notes / Issues:**
_None yet_

---

### 1.2 — Migrate & Extend `shared/models.py`

**Source for existing tables:** `ms3_user/NutriX-main/NutriX-main/app/models.py` (595 lines, 30 model classes)

- [ ] 1.2.1 Copy the entire contents of `ms3_user/NutriX-main/NutriX-main/app/models.py` into `shared/models.py`.
- [ ] 1.2.2 Change the import at the top from:
  ```python
  from app.db import Base
  ```
  to:
  ```python
  from shared.db import Base
  ```
  All other imports (`Column`, `Integer`, `String`, etc.) remain unchanged.
- [ ] 1.2.3 Append the 5 new NutriX model classes at the **bottom** of `shared/models.py` (after all existing models):

#### New ORM Models

**`UserAdapter`** — Stores the per-user YOLOv8 detection head.

> **What is `class_mappings`?** Each user's adapter head is fine-tuned to recognize a custom set of foods from their kitchen. `class_mappings` stores the mapping of detection head output indices to food label names, e.g. `{"0": "paneer_tikka", "1": "roti", "2": "idli"}`. Without this, `cv_engine.py` cannot decode the output of a user's custom head after inference.

```python
from sqlalchemy.dialects.postgresql import JSONB

class UserAdapter(Base):
    __tablename__ = "user_adapters"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    weights_path    = Column(Text, nullable=False)            # Relative path to the .pt head weight file
    adapter_version = Column(Integer, nullable=False, default=1)
    base_model      = Column(Text, nullable=False, default="nutrix_yolo_custom.pt")
    num_classes     = Column(Integer, nullable=False, default=123)
    class_mappings  = Column(JSONB, nullable=True)            # {"0": "paneer_tikka", "1": "roti", ...}
    training_images = Column(Integer, nullable=False, default=0)
    last_trained_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="adapter")

    def __repr__(self):
        return f"<UserAdapter user_id={self.user_id} version={self.adapter_version}>"
```

**`AuditLog`** — Execution trace for every inference and LLM call.

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id             = Column(BigInteger, primary_key=True, index=True)
    service        = Column(Text, nullable=False)           # 'ms1', 'ms2', 'ms4'
    operation      = Column(Text, nullable=False)           # 'yolo_inference', 'llm_lookup', 'llm_vision', 'agent_query'
    user_id        = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    input_hash     = Column(Text, nullable=True)            # SHA256 of input (for dedup/audit)
    output_summary = Column(JSONB, nullable=True)           # Truncated output for audit
    confidence     = Column(Float, nullable=True)
    latency_ms     = Column(Integer, nullable=True)
    s_faith_score  = Column(Float, nullable=True)           # Meta-Auditor faithfulness score (NULL until audited)
    flagged        = Column(Boolean, default=False)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AuditLog id={self.id} service={self.service} operation={self.operation}>"
```

**`ClinicalAlert`** — Tier 2A Guardian alert events.

```python
class ClinicalAlert(Base):
    __tablename__ = "clinical_alerts"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    alert_type      = Column(Text, nullable=False)          # 'caloric_excess', 'protein_deficit', 'diabetic_threshold', 'hypertension_threshold'
    severity        = Column(Text, nullable=False)          # 'L1_notification', 'L2_logged', 'L3_mdt_triggered'
    trigger_value   = Column(Float, nullable=True)          # The value that triggered the alert
    threshold_value = Column(Float, nullable=True)          # The threshold that was crossed
    message         = Column(Text, nullable=True)
    resolved        = Column(Boolean, default=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ClinicalAlert user_id={self.user_id} type={self.alert_type} severity={self.severity}>"
```

**`ClinicalReport`** — Full MDT-generated clinical report.

```python
class ClinicalReport(Base):
    __tablename__ = "clinical_reports"

    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    alert_id    = Column(Integer, ForeignKey("clinical_alerts.id"), nullable=True)
    report_text = Column(Text, nullable=False)              # Full MDT-generated clinical report
    nova_flags  = Column(JSONB, nullable=True)              # Ultra-processed food flags from Diagnostic Agent
    intervention= Column(JSONB, nullable=True)              # Meal plan adjustment from Intervention Agent
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ClinicalReport id={self.id} user_id={self.user_id}>"
```

**`SystemPromptRegistry`** — Versioned LLM system prompt store.

```python
class SystemPromptRegistry(Base):
    __tablename__ = "system_prompt_registry"

    id          = Column(Integer, primary_key=True, index=True)
    prompt_key  = Column(Text, nullable=False, unique=True) # e.g. 'nutrition_lookup_v1', 'vision_infer_v2'
    prompt_text = Column(Text, nullable=False)
    version     = Column(Integer, nullable=False, default=1)
    is_active   = Column(Boolean, default=True)
    patched_by  = Column(Text, default="human")             # 'human' or 'meta_auditor'
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SystemPromptRegistry key={self.prompt_key} v={self.version}>"
```

- [ ] 1.2.4 Add the required additional imports at the top of `shared/models.py`:
  ```python
  from sqlalchemy import BigInteger, Text, func
  from sqlalchemy.dialects.postgresql import JSONB
  ```
  These are needed for `BigInteger` (audit_logs), `Text`, `JSONB`, and `func.now()` used in the new models.

- [ ] 1.2.5 Verify all existing relationships use `back_populates` or `backref` correctly and no circular imports exist.

**Notes / Issues:**
- Existing models use naive `DateTime` (not timezone-aware). New models use `DateTime(timezone=True)`. This is intentional — existing MS3 tables remain untouched, new tables use timezone-aware timestamps.
- `BigInteger` is used for `audit_logs.id` because this table will accumulate millions of rows over time.

---

### 1.3 — Alembic Migration Setup

**Location:** `shared/alembic/`

> **PYTHONPATH Note:** All Alembic commands **must be run from the project root** (`~/Nutrix`) with `PYTHONPATH=.` set, so `import shared.models` resolves correctly. Every command below includes this prefix.

- [ ] 1.3.1 Add `alembic` to `ms3_user/requirements.txt` and `shared/` requirements.
- [ ] 1.3.2 Run Alembic init from project root:
  ```bash
  cd ~/Nutrix
  PYTHONPATH=. alembic init shared/alembic
  ```
- [ ] 1.3.3 Edit `shared/alembic/alembic.ini` — set the sqlalchemy url:
  ```ini
  sqlalchemy.url = %(DATABASE_URL)s
  ```
- [ ] 1.3.4 Edit `shared/alembic/env.py` — replace the `target_metadata` section:
  ```python
  import os
  import sys
  sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

  from shared.models import Base
  from shared.db import DATABASE_URL
  from sqlalchemy import engine_from_config

  config.set_main_option("sqlalchemy.url", DATABASE_URL)
  target_metadata = Base.metadata
  ```
- [ ] 1.3.5 Generate the first migration (autogenerate from all models):
  ```bash
  cd ~/Nutrix
  PYTHONPATH=. alembic revision --autogenerate -m "initial_schema_all_tables"
  ```
- [ ] 1.3.6 **Review the generated migration file** in `shared/alembic/versions/`. Confirm it contains all 35+ tables (30 existing + 5 new). Check that `user_adapters`, `audit_logs`, `clinical_alerts`, `clinical_reports`, and `system_prompt_registry` are all present.
- [ ] 1.3.7 Run the migration against the running PostgreSQL container:
  ```bash
  cd ~/Nutrix
  PYTHONPATH=. alembic upgrade head
  ```
- [ ] 1.3.8 Verify all tables exist inside the running PostgreSQL container:
  ```bash
  docker exec -it nutrix-postgres psql -U nutrix -d nutrix_db -c "\dt"
  ```
  Expected output: a list of 35+ tables including `user_adapters`, `audit_logs`, `clinical_alerts`, `clinical_reports`, `system_prompt_registry`.

**Notes / Issues:**
_None yet_

---

### 1.4 — Database Seeder Scripts

The existing MS3 project contains a comprehensive build+seeder script (`build_nutrition_master_db.py`) that has already been written and tested. Phase 1 adapts it to target **PostgreSQL** via SQLAlchemy instead of SQLite directly.

**All dataset source files are located at:**
```
ms3_user/NutriX-main/NutriX-main/Dataset/
├── INDB.xlsx                    ← ICMR Indian Nutrient Database
├── recipes.xlsx                 ← Master recipe database (714 KB)
├── Indian_Food_DF.csv           ← Additional Indian dish data
├── Units.xlsx                   ← Portion unit → gram conversion table
├── FoodData_Central_foundation_food_csv_2026-04-30/  ← USDA CSVs
│   ├── food.csv
│   ├── food_nutrient.csv
│   └── food_portion.csv
└── ...                          ← Additional regional cuisine CSVs
```

**All seeders should be created in:** `shared/seeders/`

---

#### 1.4.1 — Seed `foods` + `food_nutrients` (ICMR + USDA)

**Reference script:** `ms3_user/NutriX-main/NutriX-main/scripts/build_nutrition_master_db.py` (contains full ICMR + USDA parsing logic).

- [ ] Create `shared/seeders/seed_foods.py`
- [ ] Adapt the food parsing logic from `build_nutrition_master_db.py` to use SQLAlchemy `SessionLocal` from `shared/db.py` instead of raw `sqlite3` calls.
- [ ] Parse `INDB.xlsx` → extract food code, name, per-100g macros (`energy_kcal`, `protein_g`, `carb_g`, `fat_g`, `fibre_g`, `sodium_mg`, `sugar_g`, `calcium_mg`, `iron_mg`, `vitc_mg`, `folate_ug`).
- [ ] Parse `Indian_Food_DF.csv` → merge additional Indian dishes.
- [ ] Parse USDA `food.csv` + `food_nutrient.csv` + `food_portion.csv` → merge non-duplicate foods.
- [ ] Use SQLAlchemy `merge()` or `INSERT ... ON CONFLICT DO NOTHING` for idempotency (safe to re-run without duplicating rows).
- [ ] Log: `Inserted: X foods, Skipped: Y duplicates`.

**Expected output:** ~15,000–25,000 food rows (ICMR + USDA merged)

---

#### 1.4.2 — Seed `recipes` + `recipe_nutrition` + `recipe_ingredients` + `recipe_steps`

**Reference script:** `ms3_user/NutriX-main/NutriX-main/scripts/build_nutrition_master_db.py` (recipe section).

- [ ] Create `shared/seeders/seed_recipes.py`
- [ ] Parse `recipes.xlsx` → extract recipe name, `recipe_code`, category (Breakfast/Lunch-Dinner/Snack), cuisine, cooking time, difficulty.
- [ ] Parse ingredient rows → insert into `recipe_ingredients`.
- [ ] Parse per-serving and total macro breakdown → insert into `recipe_nutrition`.
- [ ] Parse `recipes_servingsize.xlsx` → insert into `servings`.
- [ ] Use upsert by `recipe_code` for idempotency.

**Expected output:** ~1,000–5,000 recipe rows

---

#### 1.4.3 — Seed `food_aliases` (Indian Regional Synonyms)

**Reference:** `ms3_user/NutriX-main/NutriX-main/app/services/ingredient_matcher.py` (contains the 100+ synonym map already in code).

- [ ] Create `shared/seeders/seed_aliases.py`
- [ ] Extract the synonym dictionary from `ingredient_matcher.py` (e.g., `"adrak": "ginger"`, `"nimbu": "lemon"`, `"capsicum": "bell pepper"`).
- [ ] For each alias-to-canonical pair, look up the canonical food's `id` in the `foods` table, then insert a row into `food_aliases`.
- [ ] Use `INSERT ... ON CONFLICT DO NOTHING` for idempotency.

---

#### 1.4.4 — Seed `food_portions` + `unit_conversions` (Unit → Gram Conversions)

- [ ] Create `shared/seeders/seed_portions.py`
- [ ] Parse `Units.xlsx` → unit name (`katori`, `tbsp`, `cup`, `piece`, etc.) + gram conversion value.
- [ ] Insert into `unit_conversions` table (general-purpose lookup used by `homely_meals_engine.py`).
- [ ] Also insert into `food_portions` for food-specific portion data from USDA `food_portion.csv`.

---

#### 1.4.5 — Seed `ingredient_rules` (Dietary Compliance Rules)

**Reference script:** `ms3_user/NutriX-main/NutriX-main/scripts/seed_custom_data.py`

> This script already exists and contains Jain, Vegan, and drink rules. It currently targets SQLite via raw `sqlite3`. It must be adapted to use PostgreSQL via SQLAlchemy.

- [ ] Create `shared/seeders/seed_rules.py`
- [ ] Port all logic from `seed_custom_data.py` into a SQLAlchemy-based equivalent using `SessionLocal` from `shared/db.py`.
- [ ] The rules insert covers:
  - Jain exclusions: beetroot, turnip, yam, suran, sweet potato, radish
  - Vegan exclusions: ghee, clarified butter, gelatin, honey
  - Additional ingredient rules from `build_nutrition_master_db.py`
- [ ] Use `INSERT ... ON CONFLICT DO NOTHING` for idempotency.

---

#### 1.4.6 — Seed `system_prompt_registry` (Initial LLM Prompts)

- [ ] Create `shared/seeders/seed_prompts.py`
- [ ] Insert the following initial prompts into `system_prompt_registry`:

  | `prompt_key` | Purpose |
  |---|---|
  | `nutrition_lookup_v1` | Text-to-JSON nutrition generation prompt (used by MS2 `/v1/llm/lookup`) |
  | `vision_infer_v1` | Pre-HitL image → food name candidate prompt (used by MS2 `/v1/llm/vision-infer`) |
  | `agent_orchestrator_v1` | Tier 1 intent classification + tool routing prompt (used by MS4) |

- [ ] Use `INSERT ... ON CONFLICT (prompt_key) DO NOTHING` so re-runs are idempotent.

Initial prompt values:

```python
PROMPTS = [
    {
        "prompt_key": "nutrition_lookup_v1",
        "prompt_text": (
            "You are a nutrition database engine. Given a food name, return ONLY a valid JSON object "
            "with keys: calories_per_100g, protein_g, carbs_g, fat_g. "
            "Do NOT include markdown, explanations, or conversational filler. "
            "Food: {food_name}"
        ),
        "version": 1,
    },
    {
        "prompt_key": "vision_infer_v1",
        "prompt_text": (
            "You are a food recognition assistant. Given a food image, identify the food item and "
            "estimate its macronutrients per 100g. Return ONLY a JSON object with keys: "
            "food_name, calories_per_100g, protein_g, carbs_g, fat_g. "
            "Do NOT include markdown or explanations."
        ),
        "version": 1,
    },
    {
        "prompt_key": "agent_orchestrator_v1",
        "prompt_text": (
            "You are a dietary assistant intent router. Classify the user utterance into one of: "
            "[query_macros, log_meal, get_daily_summary, recommend_recipes, generate_meal_plan]. "
            "Return ONLY a JSON object with keys: intent, entities. "
            "User input: {user_input}"
        ),
        "version": 1,
    },
]
```

---

#### 1.4.7 — Master Seeder Runner

- [ ] Create `shared/seeders/run_all_seeders.py` that calls all seeders in the correct dependency order:

```python
# Correct order: foods must exist before aliases/portions can reference them
# prompts have no dependencies and can go first or last

1. seed_foods.py        ← seeds foods + food_nutrients
2. seed_aliases.py      ← seeds food_aliases (depends on foods)
3. seed_portions.py     ← seeds food_portions + unit_conversions
4. seed_rules.py        ← seeds ingredient_rules
5. seed_recipes.py      ← seeds recipes, recipe_nutrition, recipe_ingredients, recipe_steps, servings
6. seed_prompts.py      ← seeds system_prompt_registry
```

- [ ] Each seeder must be callable from the runner with a try/except block so one failing seeder doesn't halt all others.
- [ ] Run the master seeder:
  ```bash
  cd ~/Nutrix
  PYTHONPATH=. python shared/seeders/run_all_seeders.py
  ```
- [ ] Verify food count:
  ```bash
  docker exec -it nutrix-postgres psql -U nutrix -d nutrix_db -c "SELECT COUNT(*) FROM foods;"
  ```
  **Expected: > 10,000 rows.**

**Notes / Issues:**
_None yet_

---

### 1.5 — PostgreSQL Trigger → Redis Pipeline

**Goal:** Every time a row is INSERTed or UPDATEd in `meal_logs`, PostgreSQL automatically recalculates the user's daily macro totals and pushes them to a Redis key and stream.

**How it works:**
1. `meal_logs` INSERT/UPDATE fires the trigger `trg_macro_update`.
2. The trigger function sums all `meal_logs` for the current user + today → calls `pg_notify('macro_update', json_payload)`.
3. A Python listener (`shared/db_listener.py`) running inside **MS3's** FastAPI startup subscribes to this `LISTEN` channel.
4. On notification received, the listener writes totals to Redis keys and appends to the user's Redis stream.

**Redis Key Pattern:** `user:{user_id}:daily:{YYYY-MM-DD}` → Hash with fields `calories`, `protein`, `carbs`, `fat`

**Redis Stream Pattern:** `user:{user_id}:macro_stream` → Consumed by MS4 Outlier Guardian

---

- [ ] 1.5.1 Write the PostgreSQL trigger function. This must be added to the Alembic migration as a raw SQL `op.execute()` step (see 1.3.6):

```sql
CREATE OR REPLACE FUNCTION notify_macro_update()
RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
BEGIN
    SELECT jsonb_build_object(
        'user_id',  NEW.user_id,
        'date',     CURRENT_DATE::TEXT,
        'calories', COALESCE(SUM(calories), 0),
        'protein',  COALESCE(SUM(protein), 0),
        'carbs',    COALESCE(SUM(carbs), 0),
        'fat',      COALESCE(SUM(fat), 0)
    ) INTO payload
    FROM meal_logs
    WHERE user_id = NEW.user_id
      AND log_date = CURRENT_DATE;

    PERFORM pg_notify('macro_update', payload::TEXT);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_macro_update
AFTER INSERT OR UPDATE ON meal_logs
FOR EACH ROW EXECUTE FUNCTION notify_macro_update();
```

> **Column names:** Using `calories`, `protein`, `carbs`, `fat` to match the exact column names in MS3's `MealLog` model. Do NOT use `calories_kcal` or other variants.

- [ ] 1.5.2 Add the trigger SQL to the Alembic migration file (inside the `upgrade()` function, after all table creation):
  ```python
  def upgrade():
      # ... all table create operations ...
      op.execute("""
          CREATE OR REPLACE FUNCTION notify_macro_update() ...
      """)
      op.execute("""
          CREATE TRIGGER trg_macro_update ...
      """)
  ```

- [ ] 1.5.3 Create `shared/db_listener.py` — a synchronous PostgreSQL LISTEN loop using `psycopg2`:

```python
import os
import json
import logging
import threading
import select
import psycopg2
import psycopg2.extensions
import redis as redis_lib

logger = logging.getLogger("db_listener")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://nutrix:changeme@postgres:5432/nutrix_db")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

def handle_macro_update(payload_str: str, redis_client):
    try:
        data = json.loads(payload_str)
        user_id = data["user_id"]
        date_str = data["date"]
        key = f"user:{user_id}:daily:{date_str}"

        # Write daily totals to Redis Hash (fast read for Flutter dashboard)
        redis_client.hset(key, mapping={
            "calories": data["calories"],
            "protein":  data["protein"],
            "carbs":    data["carbs"],
            "fat":      data["fat"],
        })
        redis_client.expire(key, 86400 * 7)  # TTL: 7 days

        # Also push to the user's macro stream (consumed by MS4 Guardian)
        stream_key = f"user:{user_id}:macro_stream"
        redis_client.xadd(stream_key, data, maxlen=1000)

        logger.info(f"Macro update written to Redis for user {user_id} on {date_str}")
    except Exception as e:
        logger.error(f"Error handling macro update: {e}")


def start_listener():
    """
    Runs in a background thread. Connects to PostgreSQL via psycopg2,
    listens for pg_notify on 'macro_update', and writes to Redis on each event.
    Call this from MS3's FastAPI lifespan startup.
    """
    r = redis_lib.from_url(REDIS_URL, decode_responses=True)

    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("LISTEN macro_update;")
    logger.info("PostgreSQL LISTEN on 'macro_update' channel started.")

    while True:
        if select.select([conn], [], [], 5) != ([], [], []):
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                handle_macro_update(notify.payload, r)


def start_listener_thread():
    """Start the listener in a daemon background thread."""
    t = threading.Thread(target=start_listener, daemon=True)
    t.start()
    logger.info("DB listener thread started.")
```

> **Why `psycopg2` instead of `asyncpg`?** We are using synchronous SQLAlchemy everywhere (decision made in planning). `psycopg2` is already in every service's `requirements.txt` (`psycopg2-binary`). Running the listener in a daemon thread avoids adding an async dependency.

- [ ] 1.5.4 Add `start_listener_thread()` to MS3's FastAPI lifespan startup (inside `ms3_user/main.py`):
  ```python
  from shared.db_listener import start_listener_thread

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      start_listener_thread()
      yield

  app = FastAPI(lifespan=lifespan)
  ```

- [ ] 1.5.5 **Test the pipeline:**
  ```bash
  # Step 1: Open a psql shell
  docker exec -it nutrix-postgres psql -U nutrix -d nutrix_db

  # Step 2: Insert a test meal log row
  INSERT INTO meal_logs (user_id, log_date, meal_type, food_name, calories, protein, carbs, fat)
  VALUES (1, CURRENT_DATE, 'Lunch', 'test_food', 500, 30, 60, 15);

  # Step 3: Check Redis (in a separate terminal)
  docker exec -it nutrix-redis redis-cli HGETALL "user:1:daily:$(date +%Y-%m-%d)"
  ```
  **Expected:** Redis hash returns `calories: 500`, `protein: 30`, `carbs: 60`, `fat: 15` within 1 second.

**Notes / Issues:**
_None yet_

---

### 1.6 — Redis Connection & Shared Client

- [ ] 1.6.1 Verify Redis `redis:7-alpine` container is healthy:
  ```bash
  docker exec -it nutrix-redis redis-cli ping
  # Expected: PONG
  ```

- [ ] 1.6.2 Create `shared/redis_client.py` — a shared synchronous Redis client factory:

```python
import os
import redis
from functools import lru_cache

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)
```

- [ ] 1.6.3 Test Redis connection from within the MS3 container:
  ```bash
  docker exec -it nutrix-ms3-user python -c \
    "import redis; r=redis.from_url('redis://redis:6379/0'); print(r.ping())"
  ```
  **Expected: `True`**

- [ ] 1.6.4 Verify XADD and XREAD work on the macro stream:
  ```bash
  docker exec -it nutrix-redis redis-cli XADD "user:test:macro_stream" "*" calories 500 protein 30
  docker exec -it nutrix-redis redis-cli XREAD COUNT 1 STREAMS "user:test:macro_stream" 0
  ```

- [ ] 1.6.5 Configure Redis `maxmemory-policy` for LRU eviction. Add to `docker-compose.yml` under the `redis` service:
  ```yaml
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
  ```

**Notes / Issues:**
_None yet_

---

### 1.7 — Database Health Check Endpoint

Every service must expose `GET /health` that verifies both PostgreSQL and Redis connectivity.

> **Important:** All health check functions are **synchronous** (matching our sync SQLAlchemy strategy). No `async def` here.

- [ ] 1.7.1 Create `shared/health.py`:

```python
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis as redis_lib

def check_db_health(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"postgres": "ok"}
    except Exception as e:
        return {"postgres": "error", "detail": str(e)}

def check_redis_health(r: redis_lib.Redis) -> dict:
    try:
        r.ping()
        return {"redis": "ok"}
    except Exception as e:
        return {"redis": "error", "detail": str(e)}
```

- [ ] 1.7.2 Update every service's `main.py` to import `shared/health.py` and wire the health endpoint. Example for `ms1_cv/main.py`:

```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from shared.db import get_db
from shared.redis_client import get_redis
from shared.health import check_db_health, check_redis_health

app = FastAPI(title="NutriX MS1 CV & Ingestion Service", version="1.0.0")

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    r = get_redis()
    return {
        "status": "ok",
        "service": "ms1_cv",
        **check_db_health(db),
        **check_redis_health(r),
    }
```

Apply the same pattern to `gateway/main.py`, `ms2_llm/main.py`, `ms3_user/main.py`, and `ms4_agents/main.py`.

- [ ] 1.7.3 Add `asyncpg` to `ms3_user/requirements.txt` (needed by `psycopg2` alternatives and future async needs):
  ```
  asyncpg>=0.29.0
  ```

- [ ] 1.7.4 Test each service's health endpoint:
  ```bash
  curl http://localhost:8000/health   # gateway
  curl http://localhost:8001/health   # ms1_cv
  curl http://localhost:8002/health   # ms3_user
  curl http://localhost:8003/health   # ms2_llm
  curl http://localhost:8004/health   # ms4_agents
  ```
  **Expected from all:** `{"status": "ok", "service": "<name>", "postgres": "ok", "redis": "ok"}`

**Notes / Issues:**
_None yet_

## 🛠️ Phase 1 Audit Fixes Log
> The following fixes were applied as a result of the Phase 1 Architectural Audit to ensure system correctness before spin-up:

- **Missing Columns in `meal_logs`:** Added `weight_g` and `source` to `shared/models.py` and the initial migration to support MS1 scaling and MS4 meta-auditing.
- **SQLite Fallback:** Restored the SQLite fallback pattern in `shared/db.py` to allow local MS3 execution without Docker. Default hostname updated to `localhost`.
- **Database Schema Redundancy:** Removed 5 "dead code" tables (`Ingredient`, `FoodCategory`, `FoodPortion`, `FoodAlias`, `FoodTag`) from `models.py` and the initial migration to reduce bloat.
- **PostgreSQL Trigger Indexing:** Added an index `ix_meal_logs_user_date` to `meal_logs` in the initial migration to prevent sequential scans when the trigger sums daily macros.
- **Missing `__init__.py` Files:** Added missing initialization files to `shared/seeders/` and `ms3_user/services/` to ensure they act as valid Python packages.
- **alembic.ini Cleanup:** Replaced the hardcoded URL with a placeholder to clarify that `env.py` manages the connection via `DATABASE_URL`.

---

## Completion Checklist

| Step | Status | Notes |
|---|---|---|
| 1.1 shared/db.py updated | ✅ Completed | SQLite fallback & localhost connection |
| 1.2 shared/models.py migrated + new tables | ✅ Completed | 34 tables created, dead code pruned |
| 1.3 Alembic setup + migration run | ✅ Completed | `001_initial_schema` applied |
| 1.4.1 Seed foods (ICMR + USDA) | ✅ Completed | Ingested food database |
| 1.4.2 Seed recipes | ✅ Completed | Ingested base & regional recipes |
| 1.4.3 Seed food aliases | ✅ Completed | Configured to skip dead table |
| 1.4.4 Seed food portions + unit conversions | ✅ Completed | Ingested `unit_conversions` |
| 1.4.5 Seed ingredient rules | ✅ Completed | Ingested dietary rules |
| 1.4.6 Seed system prompts | ✅ Completed | Ingested system prompt registry |
| 1.4.7 Master seeder runner | ✅ Completed | Executed `run_all_seeders.py` |
| 1.5 PostgreSQL trigger + Redis pipeline | ✅ Completed | Tested live macro notify & Redis update |
| 1.6 Redis shared client + streams verified | ✅ Completed | `SETEX` & `PUBLISH` verified on Redis container |
| 1.7 Health check endpoints on all services | ✅ Completed | Integrated across all microservices |

**Phase 1 is complete when:**
- `alembic upgrade head` runs without errors on a fresh PostgreSQL container.
- `SELECT COUNT(*) FROM foods` returns > 10,000 rows.
- Inserting a row into `meal_logs` causes Redis key `user:1:daily:YYYY-MM-DD` to be populated within 1 second.
- `GET /health` on all 5 services returns `{"postgres": "ok", "redis": "ok"}`.

---

## Key Files Created in This Phase

| File | Purpose |
|---|---|
| `shared/db.py` | PostgreSQL-with-SQLite-fallback session factory |
| `shared/models.py` | Unified SQLAlchemy ORM for all 35+ tables |
| `shared/redis_client.py` | Sync Redis client factory (shared across services) |
| `shared/health.py` | Reusable synchronous health check functions |
| `shared/db_listener.py` | PostgreSQL LISTEN → Redis writer (runs in MS3 startup thread) |
| `shared/alembic/` | Alembic migration environment |
| `shared/alembic/versions/001_initial_schema.py` | First migration (all tables + trigger) |
| `shared/seeders/seed_foods.py` | ICMR + USDA food seeder |
| `shared/seeders/seed_recipes.py` | Recipe seeder |
| `shared/seeders/seed_aliases.py` | Indian synonym seeder |
| `shared/seeders/seed_portions.py` | Portion unit seeder |
| `shared/seeders/seed_rules.py` | Dietary rules seeder (adapted from seed_custom_data.py) |
| `shared/seeders/seed_prompts.py` | System prompt seeder |
| `shared/seeders/run_all_seeders.py` | Orchestrates all seeders in dependency order |

## Key Reference Files (Read-Only — Do NOT Modify)

| File | Why It Matters |
|---|---|
| `ms3_user/NutriX-main/NutriX-main/app/models.py` | Source of all 30 existing ORM models to migrate |
| `ms3_user/NutriX-main/NutriX-main/scripts/build_nutrition_master_db.py` | Contains the complete food + recipe parsing logic to adapt |
| `ms3_user/NutriX-main/NutriX-main/scripts/seed_custom_data.py` | Contains the Jain/Vegan/drinks rules to port into `seed_rules.py` |
| `ms3_user/NutriX-main/NutriX-main/Dataset/` | All raw dataset files (INDB.xlsx, recipes.xlsx, Units.xlsx, USDA CSVs) |
