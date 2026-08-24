import os
import json
import select
import threading
import logging
import psycopg2
import psycopg2.extensions
from shared.db import DATABASE_URL
from shared.redis_client import set_daily_macros, publish_event

logger = logging.getLogger("ms3.macro_listener")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

_listener_thread = None
_stop_event = threading.Event()

def run_macro_listener():
    logger.info("Starting PostgreSQL NOTIFY macro_update listener thread...")
    # Convert SQLAlchemy URL to raw psycopg2 connection string
    db_url = DATABASE_URL
    if db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
    elif db_url.startswith("sqlite"):
        logger.warning("SQLite in use; PostgreSQL LISTEN/NOTIFY is disabled.")
        return

    try:
        conn = psycopg2.connect(db_url)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        cursor.execute("LISTEN macro_update;")
        logger.info("Listening on PostgreSQL channel 'macro_update'...")

        while not _stop_event.is_set():
            if select.select([conn], [], [], 2) == ([], [], []):
                continue
            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                logger.debug(f"Received notification on {notify.channel}: {notify.payload}")
                try:
                    payload = json.loads(notify.payload)
                    user_id = payload.get("user_id")
                    date_str = payload.get("date")
                    if user_id and date_str:
                        # 1. Update Redis cache
                        set_daily_macros(user_id, date_str, payload)
                        # 2. Publish to Redis channel for live UI websocket subscribers
                        publish_event(f"macro_updates:{user_id}", payload)
                        logger.info(f"Updated live macros for user {user_id} on {date_str}: {payload}")
                except Exception as e:
                    logger.error(f"Error processing macro_update payload: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"PostgreSQL NOTIFY listener encountered error: {e}", exc_info=True)
    finally:
        logger.info("PostgreSQL NOTIFY listener stopped.")

def start_macro_listener_thread():
    global _listener_thread
    if _listener_thread is None or not _listener_thread.is_alive():
        _stop_event.clear()
        _listener_thread = threading.Thread(target=run_macro_listener, daemon=True, name="MacroListenerThread")
        _listener_thread.start()
        logger.info("Macro listener thread launched.")

def stop_macro_listener_thread():
    global _listener_thread
    _stop_event.set()
    if _listener_thread and _listener_thread.is_alive():
        _listener_thread.join(timeout=3)
        logger.info("Macro listener thread terminated.")

if __name__ == "__main__":
    run_macro_listener()
