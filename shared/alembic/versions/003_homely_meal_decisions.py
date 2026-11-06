"""homely_meal_decisions: per-user approve/reject of community homely meals

Revision ID: 003_homely_meal_decisions
Revises: 002_ms3_regional
Create Date: 2026-10-30 10:00:00.000000

Approval used to be one global flag on homely_meals.status, so the first user to approve or reject a shared recipe
decided it for everybody. Each user's decision now lives in its own row (unique per meal and user). homely_meals.status
is no longer changed by users: 'approved' keeps meaning "curated, visible to everyone" (the seeded meals), 'pending'
means "shared, awaiting each user's own decision".

Idempotent (IF NOT EXISTS), so it is safe on a database whose tables were created outside Alembic.
"""
from typing import Sequence, Union
from alembic import op

revision: str = '003_homely_meal_decisions'
down_revision: Union[str, None] = '002_ms3_regional'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS homely_meal_decisions (
            id SERIAL PRIMARY KEY,
            meal_id INTEGER NOT NULL REFERENCES homely_meals(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            decision VARCHAR NOT NULL,
            comment TEXT,
            decided_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT uq_homely_decision_meal_user UNIQUE (meal_id, user_id)
        )""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_homely_meal_decisions_meal_id ON homely_meal_decisions (meal_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_homely_meal_decisions_user_id ON homely_meal_decisions (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS homely_meal_decisions")
