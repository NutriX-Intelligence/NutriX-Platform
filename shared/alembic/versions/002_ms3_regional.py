"""ms3_regional: MS3 schema delta + canonical macro trigger

Revision ID: 002_ms3_regional
Revises: 001_initial_schema
Create Date: 2026-10-28 10:00:00.000000

* users.is_onboarded, profiles.water_target_ml, recipes.brand / dietary_tag (fast food)
* new tables food_categories, food_portions, food_tags, ingredients
* notify_macro_update(): payload now uses the canonical keys shared with
  shared/macro_sync.py (protein_g, carbs_g, fat_g, meals_count, latest_item), uses the
  row's own log_date (not CURRENT_DATE) and also fires on DELETE.

Everything is idempotent (IF NOT EXISTS) so it is safe on a database whose tables were
created outside Alembic.
"""
from typing import Sequence, Union
from alembic import op

revision: str = '002_ms3_regional'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CANONICAL_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION notify_macro_update()
RETURNS TRIGGER AS $$
DECLARE
    uid     INTEGER;
    d       DATE;
    payload JSONB;
BEGIN
    IF TG_OP = 'DELETE' THEN
        uid := OLD.user_id;
        d   := OLD.log_date;
    ELSE
        uid := NEW.user_id;
        d   := NEW.log_date;
    END IF;

    SELECT jsonb_build_object(
        'user_id',     uid,
        'date',        d::TEXT,
        'calories',    ROUND(COALESCE(SUM(calories), 0)::numeric, 2),
        'protein_g',   ROUND(COALESCE(SUM(protein), 0)::numeric, 2),
        'carbs_g',     ROUND(COALESCE(SUM(carbs), 0)::numeric, 2),
        'fat_g',       ROUND(COALESCE(SUM(fat), 0)::numeric, 2),
        'meals_count', COUNT(*),
        'latest_item', (SELECT food_name FROM meal_logs
                         WHERE user_id = uid AND log_date = d
                         ORDER BY id DESC LIMIT 1),
        'updated_at',  NOW()::TEXT
    ) INTO payload
    FROM meal_logs
    WHERE user_id = uid AND log_date = d;

    PERFORM pg_notify('macro_update', payload::TEXT);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;
"""

# The function created by 001 (restored on downgrade)
LEGACY_TRIGGER_FN = """
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
"""


def upgrade() -> None:
    # ── columns ───────────────────────────────────────────────────────────
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_onboarded BOOLEAN DEFAULT FALSE")
    # Anyone who already completed a profile counts as onboarded
    op.execute("""
        UPDATE users SET is_onboarded = TRUE
        WHERE COALESCE(is_onboarded, FALSE) = FALSE
          AND id IN (SELECT user_id FROM profiles WHERE age IS NOT NULL AND target_calories IS NOT NULL)
    """)
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS water_target_ml DOUBLE PRECISION")
    op.execute("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS brand VARCHAR")
    op.execute("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS dietary_tag VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recipes_brand ON recipes (brand)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_recipes_dietary_tag ON recipes (dietary_tag)")

    # ── new tables ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS food_categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE
        )""")
    op.execute("""
        CREATE TABLE IF NOT EXISTS food_portions (
            id SERIAL PRIMARY KEY,
            food_id INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
            amount DOUBLE PRECISION,
            unit VARCHAR,
            gram_weight DOUBLE PRECISION
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_food_portions_food_id ON food_portions (food_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS food_tags (
            id SERIAL PRIMARY KEY,
            food_id INTEGER NOT NULL REFERENCES foods(id) ON DELETE CASCADE,
            tag VARCHAR NOT NULL
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_food_tags_food_id ON food_tags (food_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE,
            food_code VARCHAR
        )""")

    # ── live macro trigger (canonical payload, DELETE aware) ──────────────
    op.execute(CANONICAL_TRIGGER_FN)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_macro_update ON meal_logs;
        CREATE TRIGGER trg_macro_update
        AFTER INSERT OR UPDATE OR DELETE ON meal_logs
        FOR EACH ROW EXECUTE FUNCTION notify_macro_update();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_macro_update ON meal_logs")
    op.execute(LEGACY_TRIGGER_FN)
    op.execute("""
        CREATE TRIGGER trg_macro_update
        AFTER INSERT OR UPDATE ON meal_logs
        FOR EACH ROW EXECUTE FUNCTION notify_macro_update();
    """)

    for table in ("ingredients", "food_tags", "food_portions", "food_categories"):
        op.execute(f"DROP TABLE IF EXISTS {table}")

    op.execute("DROP INDEX IF EXISTS ix_recipes_dietary_tag")
    op.execute("DROP INDEX IF EXISTS ix_recipes_brand")
    op.execute("ALTER TABLE recipes DROP COLUMN IF EXISTS dietary_tag")
    op.execute("ALTER TABLE recipes DROP COLUMN IF EXISTS brand")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS water_target_ml")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_onboarded")
