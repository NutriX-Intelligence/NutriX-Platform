"""
Authentication / authorisation dependencies for MS3.

* `get_current_user`  validates the Bearer JWT (sub = numeric user id) and, when the gateway injected
  `X-User-ID`, requires it to match the token. MS3 therefore stays safe even if reached directly.
* `enforce_ownership` rejects (403) any request that names a *different* user in the path, the query
  string or a JSON body (`user_id`, `creator_id`, `reviewer_id`). Multipart forms and delete-by-id
  routes are handled inside their handlers.
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from shared import models
from shared.db import get_db
from ms3_user.services.auth_service import decode_access_token

_bearer = HTTPBearer(auto_error=False)

_BODY_ID_KEYS = ("user_id", "creator_id", "reviewer_id")


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None:
        raise _unauthorized("Missing or invalid Authorization header")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise _unauthorized()

    sub = payload.get("sub")
    if sub is None or not str(sub).isdigit():
        # e.g. a token issued by the old standalone MS3 (sub = e-mail): sign in again
        raise _unauthorized("Token is not valid for this service. Please sign in again.")
    user_id = int(sub)

    forwarded = request.headers.get("x-user-id")
    if forwarded and forwarded != str(user_id):
        raise _unauthorized("Token does not match the forwarded user.")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None or user.is_active is False:
        raise _unauthorized("User not found")
    return user


async def enforce_ownership(request: Request, current_user: models.User = Depends(get_current_user)) -> None:
    uid = str(current_user.id)

    def check(value, where: str) -> None:
        if value is None or value == "":
            return
        if str(value) != uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{where} refers to another user.",
            )

    check(request.path_params.get("user_id"), "Path user_id")
    check(request.query_params.get("user_id"), "Query user_id")

    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
        except Exception:
            body = None  # malformed JSON is reported by the endpoint's own validation
        if isinstance(body, dict):
            for key in _BODY_ID_KEYS:
                check(body.get(key), f"Body {key}")
