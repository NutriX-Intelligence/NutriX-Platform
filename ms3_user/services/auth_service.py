import os
import datetime
import logging
import jwt
import httpx
import bcrypt
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

logger = logging.getLogger("auth_service")

# Environment: anything other than "dev" is treated as production-like (strict)
ENV = os.environ.get("ENV", "prod").strip().lower()
IS_DEV = ENV == "dev"

# JWT configuration: must match the gateway (JWT_SECRET_KEY / JWT_ALGORITHM in .env)
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
_DEV_FALLBACK_SECRET = "dev-insecure-secret"  # same default as gateway/config.py
SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or ""
if not SECRET_KEY:
    if not IS_DEV:
        raise RuntimeError("JWT_SECRET_KEY must be set (same value as the gateway) unless ENV=dev")
    SECRET_KEY = _DEV_FALLBACK_SECRET
    logger.warning("JWT_SECRET_KEY not set: using the insecure development secret")
# 720 h = 30 days, the session length the existing app expects. Set JWT_EXPIRY_HOURS to change it.
ACCESS_TOKEN_EXPIRE_MINUTES = int(float(os.environ.get("JWT_EXPIRY_HOURS", "720")) * 60)

# Accepted Google OAuth client ids (web/android/ios), comma separated
GOOGLE_CLIENT_IDS = [c.strip() for c in os.environ.get("GOOGLE_CLIENT_ID", "").split(",") if c.strip()]

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Return payload if expired claim is valid
        return decoded_token
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token signature has expired.")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None

async def verify_google_id_token(id_token: str) -> Dict[str, Any]:
    """Verify Google Oauth ID Token. Uses direct Google TokenInfo endpoint.
    
    Includes a fallback/mock block for emulator testing.
    """
    # 1. Check for mock / simulated token to ease testing and simulator usage
    if IS_DEV and id_token.startswith("mock-google-"):
        prefix = id_token.replace("mock-google-", "")
        email = f"{prefix}@example.com" if "@" not in prefix else prefix
        name = prefix.split("@")[0].capitalize()
        return {
            "email": email,
            "name": name,
            "sub": f"mock-sub-{prefix}",
            "picture": "https://www.gravatar.com/avatar/"
        }
    elif IS_DEV and id_token.startswith("google_simulated_token_"):
        prefix = id_token.replace("google_simulated_token_", "")
        email = f"{prefix}@gmail.com" if "@" not in prefix else prefix
        name = prefix.split("@")[0].capitalize()
        return {
            "email": email,
            "name": name,
            "sub": f"mock-sub-{prefix}",
            "picture": "https://www.gravatar.com/avatar/"
        }

    # 2. Query Google's verification service
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                logger.error(f"Google tokeninfo API failed with code {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Google ID Token (verification failed on Google servers)."
                )
            payload = response.json()
            # Verify issuer is Google
            if payload.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token issuer."
                )
            # The token must have been issued for one of OUR client ids (otherwise any app's token would work)
            if GOOGLE_CLIENT_IDS:
                if payload.get("aud") not in GOOGLE_CLIENT_IDS:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Google token was not issued for this application."
                    )
            elif not IS_DEV:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Google sign-in is not configured (GOOGLE_CLIENT_ID)."
                )
            return payload
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            logger.error(f"Error calling Google OAuth info endpoint: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"OAuth verification server unreachable: {str(e)}"
            )
