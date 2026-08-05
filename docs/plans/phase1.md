# Phase 1 — Data & Database Foundation

> **Master Plan Reference:** Phase 1
> **Goal:** PostgreSQL is fully seeded and Redis is running. All services connect to both.
> **Status:** 🔴 Not Started
> **Depends On:** Phase 0 (Docker Compose + `.env` must be in place)

---

## Context & Ground Truth

MS3 already has a working SQLAlchemy schema running on **SQLite** (`nutrition_master.db`). The goal of Phase 1 is to:

1. Take that existing SQLAlchemy ORM and **extend** it with the new MS1 + MS4 tables (`user_adapters`, `audit_logs`, `clinical_alerts`, `clinical_reports`).
2. Wire everything to **PostgreSQL** (already referenced via `DATABASE_URL` env var).
3. Set up **Alembic** for schema versioning.
4. Write and run all **seeders** for the food, recipe, and rules datasets.
5. Set up the **PostgreSQL trigger** → Redis pipeline for live macro streaming.
6. Verify Redis Streams work.

> **Key Rule from MASTER_ARCHITECTURE.md:** The single PostgreSQL instance is the permanent master store for all services. Redis is the fast-read cache populated by DB triggers. No service should bypass this pattern.

---

## Existing Schema (From `backendCh.md` — already in MS3)

These tables are **already defined in SQLAlchemy** in the existing `app/models.py`. We keep all of them and add the new ones.

| Existing Table | Owner Service |
|---|---|
| `users` | MS3 |
| `profiles` | MS3 |
| `meal_logs` | MS3 → MS1 also writes |
| `water_logs` | MS3 |
| `weight_logs` | MS3 |
| `generated_meal_plans` | MS3 |
| `analytics` | MS3 |
| `homely_meals` | MS3 |
| `homely_meal_ingredients` | MS3 |
| `homely_meal_nutrition` | MS3 |
| `homely_meal_reviews` | MS3 |
| `homely_meal_tags` | MS3 |
| `recommendation_history` | MS3 |
| `search_history` | MS3 |
| `settings` | MS3 |
| `foods` | MS1 + MS2 write, MS3 reads |
| `food_nutrients` | MS1 + MS2 write, MS3 reads |
| `food_portions` | MS3 seeds |
| `food_aliases` | MS3 seeds |
| `food_tags` | MS3 seeds |
| `recipes` | MS3 seeds |
| `recipe_nutrition` | MS3 seeds |
| `recipe_ingredients` | MS3 seeds |
| `recipe_steps` | MS3 seeds |
| `servings` | MS3 seeds |
| `barcode_cache` | MS3 reads/writes |
| `ingredient_rules` | MS3 seeds |

---

## New Tables to Add (NutriX-specific additions for MS1 & MS4)

| New Table | Owner Service | Purpose |
|---|---|---|
| `user_adapters` | MS1 | Stores per-user YOLOv8 head adapter path + metadata |
| `audit_logs` | MS1 + MS2 | Execution trace log for every inference/LLM call |
| `clinical_alerts` | MS4 (writes) / MS3 (reads) | Tier 2A Guardian alert events per user |
| `clinical_reports` | MS4 (writes) | Full MDT clinical report documents |
| `system_prompt_registry` | MS4 | Versioned LLM system prompt store (self-healing patch target) |

---

## Steps

---

### 1.1 — Finalize Full PostgreSQL Schema

Define every column, type, constraint, index, and foreign key for all tables.

#### New Tables Schema

**`user_adapters`**
```sql
CREATE TABLE user_adapters (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    adapter_path    TEXT NOT NULL,            -- Relative path to the .pt head weight file
    base_model      TEXT NOT NULL DEFAULT 'nutrix_yolo_custom.pt',
    num_classes     INTEGER NOT NULL DEFAULT 123,
    training_images INTEGER NOT NULL DEFAULT 0,
    last_trained_at TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)                           -- One adapter row per user
);
CREATE INDEX idx_user_adapters_user_id ON user_adapters(user_id);
```

**`audit_logs`**
```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    service         TEXT NOT NULL,            -- 'ms1', 'ms2', 'ms4'
    operation       TEXT NOT NULL,            -- 'yolo_inference', 'llm_lookup', 'llm_vision', 'agent_query'
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    input_hash      TEXT,                     -- SHA256 of input (for dedup/audit)
    output_summary  JSONB,                    -- Truncated output for audit
    confidence      FLOAT,                    -- Confidence score where applicable
    latency_ms      INTEGER,                  -- Processing time
    s_faith_score   FLOAT,                    -- Meta-Auditor faithfulness score (NULL until audited)
    flagged         BOOLEAN DEFAULT FALSE,    -- True if Tier 3 flagged this trace
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_service ON audit_logs(service);
CREATE INDEX idx_audit_logs_flagged ON audit_logs(flagged);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

**`clinical_alerts`**
```sql
CREATE TABLE clinical_alerts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_type      TEXT NOT NULL,            -- 'caloric_excess', 'protein_deficit', 'diabetic_threshold', 'hypertension_threshold'
    severity        TEXT NOT NULL,            -- 'L1_notification', 'L2_logged', 'L3_mdt_triggered'
    trigger_value   FLOAT,                    -- The value that triggered the alert
    threshold_value FLOAT,                    -- The threshold that was crossed
    message         TEXT,
    resolved        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_clinical_alerts_user_id ON clinical_alerts(user_id);
CREATE INDEX idx_clinical_alerts_resolved ON clinical_alerts(resolved);
```

**`clinical_reports`**
```sql
CREATE TABLE clinical_reports (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_id        INTEGER REFERENCES clinical_alerts(id),
    report_text     TEXT NOT NULL,            -- Full MDT-generated clinical report
    nova_flags      JSONB,                    -- Ultra-processed food flags from Diagnostic Agent
    intervention    JSONB,                    -- Meal plan adjustment from Intervention Agent
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**`system_prompt_registry`**
```sql
CREATE TABLE system_prompt_registry (
    id              SERIAL PRIMARY KEY,
    prompt_key      TEXT NOT NULL UNIQUE,     -- e.g. 'nutrition_lookup_v1', 'vision_infer_v2'
    prompt_text     TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    patched_by      TEXT DEFAULT 'human',     -- 'human' or 'meta_auditor'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**Tasks:**
- [ ] 1.1.1 Document every column for all **existing** tables (audit existing `models.py` and note any missing columns vs. `backendCh.md`).
- [ ] 1.1.2 Add the 5 new tables above to the schema.
- [ ] 1.1.3 Verify all foreign key relationships are correct in the ERD.

**Notes / Issues:**
_None yet_

---

### 1.2 — Write SQLAlchemy ORM Models

Location: `shared/models.py` (shared across all services via a shared volume or package).

- [ ] 1.2.1 Copy the existing `app/models.py` from MS3 into `shared/models.py`.
- [ ] 1.2.2 Add the 5 new ORM model classes:
  - `UserAdapter`
  - `AuditLog`
  - `ClinicalAlert`
  - `ClinicalReport`
  - `SystemPromptRegistry`
- [ ] 1.2.3 Verify all relationships use `relationship()` with correct `back_populates`.
- [ ] 1.2.4 Ensure all models use `TIMESTAMPTZ` (timezone-aware) for timestamps, not naive `DateTime`.
- [ ] 1.2.5 Add `__repr__` methods to all new models for easier debugging.

**Example — UserAdapter ORM model:**
```python
class UserAdapter(Base):
    __tablename__ = "user_adapters"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    adapter_path    = Column(Text, nullable=False)
    base_model      = Column(Text, nullable=False, default="nutrix_yolo_custom.pt")
    num_classes     = Column(Integer, nullable=False, default=123)
    training_images = Column(Integer, nullable=False, default=0)
    last_trained_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="adapter")
```

**Notes / Issues:**
_None yet_

---

### 1.3 — Alembic Migration Setup

Location: `shared/alembic/`

- [ ] 1.3.1 Install Alembic: `pip install alembic`
- [ ] 1.3.2 Run `alembic init shared/alembic` to create the migration environment.
- [ ] 1.3.3 Edit `alembic.ini` to point `sqlalchemy.url` at `DATABASE_URL` from env.
- [ ] 1.3.4 Edit `shared/alembic/env.py` to import `Base` from `shared/models.py` and set `target_metadata = Base.metadata`.
- [ ] 1.3.5 Generate the first migration (creates all tables):
  ```bash
  alembic revision --autogenerate -m "initial_schema_all_tables"
  ```
- [ ] 1.3.6 Review the generated migration script — confirm all 32+ tables are captured.
- [ ] 1.3.7 Run the migration against a fresh PostgreSQL container:
  ```bash
  alembic upgrade head
  ```
- [ ] 1.3.8 Verify in `psql` that all tables exist:
  ```sql
  \dt
  ```

**Notes / Issues:**
_None yet_

---

### 1.4 — Database Seeder Scripts

These seeders populate the static reference data. They are run once (or re-run to refresh).

**Location:** `shared/seeders/`

#### 1.4.1 — Seed `foods` + `food_nutrients` (ICMR + USDA)
- [ ] Create `shared/seeders/seed_foods.py`
- [ ] Read `INDB.xlsx` (ICMR Indian Nutrient Database) → parse food name, food code, per-100g macros (kcal, protein, carbs, fat, fibre, sodium, sugar, calcium, iron, Vitamin C, folate).
- [ ] Read `Indian_Food_DF.csv` → merge additional Indian dishes.
- [ ] Read USDA FDC `food.csv` + `food_nutrient.csv` + `food_portion.csv` → parse and merge.
- [ ] Use `INSERT ... ON CONFLICT DO NOTHING` (upsert) so re-runs are idempotent.
- [ ] Log: total records inserted, total skipped (duplicate food codes).

**Expected output:** ~15,000–25,000 food rows (ICMR + USDA merged)

#### 1.4.2 — Seed `recipes` + `recipe_nutrition` + `recipe_ingredients` + `recipe_steps`
- [ ] Create `shared/seeders/seed_recipes.py`
- [ ] Read `recipes.xlsx` → parse recipe name, category, cuisine, cooking time, difficulty.
- [ ] Parse ingredient list + amounts per recipe → insert into `recipe_ingredients`.
- [ ] Parse per-serving macro breakdown → insert into `recipe_nutrition`.
- [ ] Use upsert by recipe name (or a recipe code hash).

**Expected output:** 1,000–5,000 recipe rows (from recipes.xlsx)

#### 1.4.3 — Seed `food_aliases` (Indian Regional Synonyms)
- [ ] Create `shared/seeders/seed_aliases.py`
- [ ] Seed the 100+ synonym map already defined in `ingredient_matcher.py` into the `food_aliases` table.
- [ ] Format: `{ alias: "adrak", canonical_food_id: <ginger_id> }`

#### 1.4.4 — Seed `food_portions` (Unit → Gram Conversions)
- [ ] Create `shared/seeders/seed_portions.py`
- [ ] Read `Units.xlsx` → parse unit name (katori, tbsp, cup, piece...) + gram conversion.
- [ ] Insert into `food_portions` table.

#### 1.4.5 — Seed `ingredient_rules` (Dietary Rules)
- [ ] Create `shared/seeders/seed_rules.py`
- [ ] Port the existing `seed_custom_data.py` logic (Jain/Vegan rules) to populate `ingredient_rules` in PostgreSQL.

#### 1.4.6 — Seed `system_prompt_registry` (Initial LLM Prompts)
- [ ] Create `shared/seeders/seed_prompts.py`
- [ ] Insert the initial system prompts for:
  - `nutrition_lookup_v1` — Nutrition text-to-JSON prompt template
  - `vision_infer_v1` — Pre-HitL image → food name prompt template
  - `agent_orchestrator_v1` — Tier 1 intent classification prompt

#### 1.4.7 — Master Seeder Runner
- [ ] Create `shared/seeders/run_all_seeders.py` that calls all seeders in the correct dependency order:
  1. `seed_foods.py`
  2. `seed_aliases.py`
  3. `seed_portions.py`
  4. `seed_rules.py`
  5. `seed_recipes.py`
  6. `seed_prompts.py`

**Notes / Issues:**
_None yet_

---

### 1.5 — PostgreSQL Trigger → Redis Pipeline

**Goal:** Every time a row is INSERTed into `meal_logs`, PostgreSQL automatically recalculates the user's daily macro totals and pushes them to a Redis stream.

**Trigger:** `AFTER INSERT OR UPDATE ON meal_logs`

**What the trigger does:**
1. Sums all `meal_logs` for the current user and today's date (`calories`, `protein`, `carbs`, `fat`).
2. Calls `pg_notify('macro_update', json_payload)` to emit a notification.
3. A small Python listener service (part of MS3 startup) subscribes to this `LISTEN` channel and writes the totals to Redis.

**Redis Key Pattern:** `user:{user_id}:daily:{YYYY-MM-DD}` → Hash with fields `calories`, `protein`, `carbs`, `fat`.

**Redis Stream Pattern:** `user:{user_id}:macro_stream` → Used by MS4 Outlier Guardian.

- [ ] 1.5.1 Write the PostgreSQL trigger function in SQL:
  ```sql
  CREATE OR REPLACE FUNCTION notify_macro_update()
  RETURNS TRIGGER AS $$
  DECLARE
      payload JSONB;
  BEGIN
      SELECT jsonb_build_object(
          'user_id', NEW.user_id,
          'date', CURRENT_DATE,
          'calories', COALESCE(SUM(calories), 0),
          'protein',  COALESCE(SUM(protein_g), 0),
          'carbs',    COALESCE(SUM(carbs_g), 0),
          'fat',      COALESCE(SUM(fat_g), 0)
      ) INTO payload
      FROM meal_logs
      WHERE user_id = NEW.user_id
        AND DATE(logged_at) = CURRENT_DATE;
  
      PERFORM pg_notify('macro_update', payload::TEXT);
      RETURN NEW;
  END;
  $$ LANGUAGE plpgsql;
  
  CREATE TRIGGER trg_macro_update
  AFTER INSERT OR UPDATE ON meal_logs
  FOR EACH ROW EXECUTE FUNCTION notify_macro_update();
  ```
- [ ] 1.5.2 Add this trigger to the Alembic migration (as a raw SQL `op.execute()` step).
- [ ] 1.5.3 Write `shared/db_listener.py` — an async `asyncpg.connect()` LISTEN loop:
  ```python
  # Listens on 'macro_update' channel and writes to Redis
  async def start_listener(redis_client):
      conn = await asyncpg.connect(DATABASE_URL)
      await conn.add_listener('macro_update', lambda *args: handle_update(args, redis_client))
      ...
  ```
- [ ] 1.5.4 This listener is started as a background task inside **MS3's** FastAPI `lifespan` startup.
- [ ] 1.5.5 Test: Insert a fake `meal_logs` row via `psql`, verify the Redis key updates within 1 second.

**Notes / Issues:**
_None yet_

---

### 1.6 — Redis Connection & Stream Setup

- [ ] 1.6.1 Verify Redis `redis:7-alpine` container starts via `docker-compose up redis`.
- [ ] 1.6.2 Create `shared/redis_client.py` — a shared async Redis client factory:
  ```python
  import redis.asyncio as redis
  from functools import lru_cache

  @lru_cache
  def get_redis() -> redis.Redis:
      return redis.from_url(REDIS_URL, decode_responses=True)
  ```
- [ ] 1.6.3 Test Redis connection from within a service container:
  ```bash
  docker exec -it nutrix-ms3 python -c "import redis; r=redis.from_url('redis://redis:6379'); print(r.ping())"
  ```
- [ ] 1.6.4 Verify `XADD` and `XREAD` work on `user:test:macro_stream` — this is the stream MS4 will subscribe to.
- [ ] 1.6.5 Set Redis maxmemory policy: `maxmemory-policy allkeys-lru` (via redis.conf or command-line arg in docker-compose).

**Notes / Issues:**
_None yet_

---

### 1.7 — Database Health Check Endpoint

Every service exposes `GET /health` that confirms DB + Redis connectivity.

- [ ] 1.7.1 Create `shared/health.py` with a standard health check function:
  ```python
  async def check_db_health(db: Session) -> dict:
      try:
          db.execute(text("SELECT 1"))
          return {"postgres": "ok"}
      except Exception as e:
          return {"postgres": "error", "detail": str(e)}

  async def check_redis_health(redis) -> dict:
      try:
          await redis.ping()
          return {"redis": "ok"}
      except Exception as e:
          return {"redis": "error", "detail": str(e)}
  ```
- [ ] 1.7.2 Each service's `main.py` mounts a `GET /health` route that calls both checks.
- [ ] 1.7.3 Test: `curl http://localhost:8001/health` → `{"postgres": "ok", "redis": "ok"}`

**Notes / Issues:**
_None yet_

---

## Completion Checklist

| Step | Status | Notes |
|---|---|---|
| 1.1 Full schema finalized | ⬜ Not Started | |
| 1.2 SQLAlchemy ORM models | ⬜ Not Started | |
| 1.3 Alembic setup + migration | ⬜ Not Started | |
| 1.4.1 Seed foods (ICMR + USDA) | ⬜ Not Started | |
| 1.4.2 Seed recipes | ⬜ Not Started | |
| 1.4.3 Seed food aliases | ⬜ Not Started | |
| 1.4.4 Seed food portions | ⬜ Not Started | |
| 1.4.5 Seed ingredient rules | ⬜ Not Started | |
| 1.4.6 Seed system prompts | ⬜ Not Started | |
| 1.4.7 Master seeder runner | ⬜ Not Started | |
| 1.5 PostgreSQL trigger + Redis | ⬜ Not Started | |
| 1.6 Redis streams verified | ⬜ Not Started | |
| 1.7 Health check endpoints | ⬜ Not Started | |

**Phase 1 is complete when:**
- `alembic upgrade head` runs without errors on a fresh PostgreSQL container.
- `python run_all_seeders.py` completes and `SELECT COUNT(*) FROM foods` returns > 10,000 rows.
- Inserting a row into `meal_logs` causes the Redis key `user:1:daily:YYYY-MM-DD` to be populated within 1 second.
- `GET /health` on any service returns `{"postgres": "ok", "redis": "ok"}`.

---

## Key Files Created in This Phase

| File | Purpose |
|---|---|
| `shared/models.py` | Unified SQLAlchemy ORM for all 32+ tables |
| `shared/db.py` | Session factory + `get_db()` dependency |
| `shared/redis_client.py` | Async Redis client factory |
| `shared/health.py` | Reusable health check functions |
| `shared/db_listener.py` | Async PostgreSQL LISTEN → Redis writer |
| `shared/alembic/` | Migration environment |
| `shared/alembic/versions/001_initial_schema.py` | First migration (all tables) |
| `shared/seeders/seed_foods.py` | ICMR + USDA food seeder |
| `shared/seeders/seed_recipes.py` | Recipe seeder |
| `shared/seeders/seed_aliases.py` | Indian synonym seeder |
| `shared/seeders/seed_portions.py` | Portion unit seeder |
| `shared/seeders/seed_rules.py` | Dietary rules seeder |
| `shared/seeders/seed_prompts.py` | System prompt seeder |
| `shared/seeders/run_all_seeders.py` | Orchestrates all seeders in order |
