"""
Single place that builds and writes the live daily-macro cache.

Writers (MS1 scale ingestion, MS3 manual logging, the Postgres NOTIFY listener) all produce the
same canonical payload so Redis never flips between shapes:

    {"user_id", "date", "calories", "protein_g", "carbs_g", "fat_g", "meals_count", "latest_item", "updated_at"}

`sync_daily_macros` recomputes the totals from `meal_logs` (so it is correct after inserts AND
deletes), writes `user:{id}:macros:{date}`, publishes `macro_updates:{id}` and appends to the
`user:{id}:macro_stream` Redis stream consumed by MS4.
"""
import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from shared.models import MealLog
from shared.redis_client import append_macro_stream, publish_event, set_daily_macros

logger = logging.getLogger("shared.macro_sync")


def daily_macros_payload(db: Session, user_id: int, day: date) -> Dict[str, Any]:
    meals = (
        db.query(MealLog)
        .filter(MealLog.user_id == user_id, MealLog.log_date == day)
        .order_by(MealLog.id)
        .all()
    )
    return {
        "user_id": user_id,
        "date": day.isoformat(),
        "calories": round(sum(m.calories or 0.0 for m in meals), 2),
        "protein_g": round(sum(m.protein or 0.0 for m in meals), 2),
        "carbs_g": round(sum(m.carbs or 0.0 for m in meals), 2),
        "fat_g": round(sum(m.fat or 0.0 for m in meals), 2),
        "meals_count": len(meals),
        "latest_item": meals[-1].food_name if meals else None,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


def sync_daily_macros(
    db: Session,
    user_id: int,
    day: Optional[date] = None,
    publish: bool = True,
) -> Dict[str, Any]:
    """Recompute today's (or `day`'s) totals from the DB and push them to Redis. Never raises."""
    day = day or datetime.utcnow().date()
    payload = daily_macros_payload(db, user_id, day)
    try:
        set_daily_macros(user_id, payload["date"], payload)
        if publish:
            publish_event(f"macro_updates:{user_id}", payload)
            append_macro_stream(user_id, payload)
    except Exception as e:  # Redis problems must never fail a meal log
        logger.warning("Redis macro sync skipped for user %s: %s", user_id, e)
    return payload
