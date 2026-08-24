import json
import hashlib
import logging
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from shared.db import SessionLocal
from shared.models import AuditLog

logger = logging.getLogger("shared.audit")

def compute_input_hash(data: Any) -> str:
    try:
        if isinstance(data, (dict, list)):
            serialized = json.dumps(data, sort_keys=True, default=str)
        elif isinstance(data, (bytes, bytearray)):
            return hashlib.sha256(data).hexdigest()
        else:
            serialized = str(data)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    except Exception:
        return "hash_error"

def log_audit_event(
    service: str,
    operation: str,
    user_id: Optional[int] = None,
    input_data: Any = None,
    output_data: Any = None,
    confidence: Optional[float] = None,
    latency_ms: Optional[int] = None,
    s_faith_score: Optional[float] = None,
    flagged: bool = False,
    db: Optional[Session] = None
) -> Optional[int]:
    """
    Structured audit logging helper for MS1, MS2, and MS4.
    Inserts a record into the audit_logs table for tracing, observability,
    and Meta-Auditor continuous quality assurance.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        input_hash_val = compute_input_hash(input_data) if input_data is not None else None
        
        # Ensure output summary is JSON-compatible dict or string
        if isinstance(output_data, (dict, list)):
            out_summary = output_data
        elif output_data is not None:
            out_summary = {"summary": str(output_data)[:2000]}
        else:
            out_summary = None

        audit_entry = AuditLog(
            service=service,
            operation=operation,
            user_id=user_id,
            input_hash=input_hash_val,
            output_summary=out_summary,
            confidence=confidence,
            latency_ms=latency_ms,
            s_faith_score=s_faith_score,
            flagged=flagged
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry.id
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record audit log for {service}:{operation}: {e}", exc_info=True)
        return None
    finally:
        if should_close_db:
            db.close()
