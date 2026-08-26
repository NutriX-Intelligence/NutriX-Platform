from fastapi import Request, HTTPException
from jose import jwt, JWTError
from gateway.config import JWT_SECRET_KEY, JWT_ALGORITHM
import time

def verify_jwt_token(request: Request) -> str:
    """
    Verifies JWT token from Authorization header and returns user_id.
    Raises HTTPException 401 if invalid/expired/missing.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        exp = payload.get("exp")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject (sub)")
            
        if exp and exp < int(time.time()):
            raise HTTPException(status_code=401, detail="Token expired")
            
        return str(user_id)
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
