from fastapi import Request, HTTPException
import hmac
from gateway.config import DEVICE_TOKEN

def verify_device_token(request: Request) -> str:
    """
    Verifies Device-Token header using hmac.compare_digest.
    Requires User-ID header.
    Returns user_id.
    """
    device_token = request.headers.get("Device-Token")
    user_id = request.headers.get("User-ID")
    
    if not device_token:
        raise HTTPException(status_code=401, detail="Missing Device-Token header")
        
    if not user_id:
        raise HTTPException(status_code=400, detail="Missing User-ID header")
        
    if not hmac.compare_digest(device_token.encode(), DEVICE_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Invalid Device-Token")
        
    return str(user_id)
