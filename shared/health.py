import time
import datetime
import logging
from typing import Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from shared.redis_client import get_redis_client

logger = logging.getLogger("shared.health")

def check_database(db: Session) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        db.execute(text("SELECT 1;"))
        latency = (time.perf_counter() - start) * 1000.0
        return {"status": "ok", "latency_ms": round(latency, 2)}
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000.0
        logger.error(f"Database health check failed: {e}")
        return {"status": "error", "error": str(e), "latency_ms": round(latency, 2)}

def check_redis() -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        client = get_redis_client()
        if client is None:
            return {"status": "fallback_in_memory", "latency_ms": 0.0}
        client.ping()
        latency = (time.perf_counter() - start) * 1000.0
        return {"status": "ok", "latency_ms": round(latency, 2)}
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000.0
        logger.error(f"Redis health check failed: {e}")
        return {"status": "error", "error": str(e), "latency_ms": round(latency, 2)}

def check_health(
    service_name: str,
    db: Optional[Session] = None,
    include_redis: bool = True,
    version: str = "1.0.0"
) -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    is_healthy = True
    is_degraded = False

    if db is not None:
        db_check = check_database(db)
        checks["database"] = db_check
        if db_check["status"] != "ok":
            is_healthy = False

    if include_redis:
        redis_check = check_redis()
        checks["redis"] = redis_check
        if redis_check["status"] == "error":
            is_degraded = True
        elif redis_check["status"] == "fallback_in_memory":
            is_degraded = True

    if not is_healthy:
        overall_status = "unhealthy"
    elif is_degraded:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "service": service_name,
        "version": version,
        "checks": checks,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
