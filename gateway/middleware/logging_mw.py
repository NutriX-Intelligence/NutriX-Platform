from fastapi import Request
import time
import logging
import json
import uuid
from typing import Callable, Awaitable

logger = logging.getLogger("gateway")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)

async def logging_middleware(request: Request, call_next: Callable[[Request], Awaitable]):
    start_time = time.perf_counter()
    
    # Extract or generate Request-ID
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    
    response = await call_next(request)
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    
    log_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host if request.client else "127.0.0.1",
        "status_code": response.status_code,
        "duration_ms": round(duration_ms, 2)
    }
    
    # Inject variables from router if available
    if hasattr(request.state, "user_id"):
        log_data["user_id"] = request.state.user_id
    if hasattr(request.state, "target_service"):
        log_data["target_service"] = request.state.target_service
    if hasattr(request.state, "auth_type"):
        log_data["auth_type"] = request.state.auth_type
        
    logger.info(json.dumps(log_data))
    
    return response
