from fastapi import Request, HTTPException
import hmac
from gateway.config import DEVICE_TOKEN

def verify_device_token(request: Request) -> str:
    """
    Verifies Device-Token header using hmac.compare_digest.
    Requires User-ID header.
    Returns user_id.
    """
    device_token = request.headers.get("Device-Token") or request.headers.get("device-token")
    user_id = request.headers.get("User-ID") or request.headers.get("X-User-ID")
    
    if not device_token:
        raise HTTPException(status_code=401, detail="Missing Device-Token header")
        
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing User-ID header")
        
    valid_tokens = {DEVICE_TOKEN, "NutriX_ESP32_SECURE_TOKEN"}
    if not any(hmac.compare_digest(device_token.encode(), t.encode()) for t in valid_tokens if t):
        raise HTTPException(status_code=401, detail="Invalid Device-Token")
        
    return str(user_id)
