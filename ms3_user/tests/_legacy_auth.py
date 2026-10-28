"""
Legacy-test compatibility for the ported MS3 tests.

They were written when the API was unauthenticated. For every module except test_auth_contract.py (which tests real
authentication and must stay strict) this autouse fixture attaches a valid Bearer token for the user each request
names (path / query / JSON / form / owner of a deleted log / e-mail of calculate-profile), creating that user when the
test did not. Engine and logic tests keep working; security is covered by test_auth_contract.py.
"""
import re
import urllib.parse

import pytest
from starlette.testclient import TestClient as _TestClient

from shared import db as shared_db
from shared import models
from ms3_user.services.auth_service import create_access_token

_PUBLIC_AUTH = re.compile(r"/auth/(register|login|google|reset-password)$")
_PATH_USER = re.compile(r"/(?:users|today|history|user|analytics)/(\d+)")
_DELETE_LOG = re.compile(r"/(meal-logs|water-logs|weight-logs)/(\d+)$")
_LOG_MODEL = {"meal-logs": "MealLog", "water-logs": "WaterLog", "weight-logs": "WeightLog"}


def _session():
    from ms3_user.main import app
    dep = app.dependency_overrides.get(shared_db.get_db, shared_db.get_db)
    produced = dep()
    if hasattr(produced, "__next__"):
        return next(produced), produced
    return produced, None


def _identity(method, url, kwargs):
    parts = urllib.parse.urlsplit(str(url))
    query = dict(urllib.parse.parse_qsl(parts.query))
    sources = [kwargs.get("json"), kwargs.get("data"), kwargs.get("params"), query]
    for key in ("user_id", "creator_id", "reviewer_id"):
        for src in sources:
            if isinstance(src, dict) and src.get(key) not in (None, ""):
                return {"user_id": int(src[key])}
    m = _PATH_USER.search(parts.path)
    if m:
        return {"user_id": int(m.group(1))}
    if method.upper() == "DELETE":
        d = _DELETE_LOG.search(parts.path)
        if d:
            return {"delete_log": (_LOG_MODEL[d.group(1)], int(d.group(2)))}
    for src in sources:
        if isinstance(src, dict) and src.get("email"):
            return {"email": str(src["email"])}
    return {}


def _resolve_user(ident):
    db, gen = _session()
    try:
        user = None
        if "delete_log" in ident:
            model_name, log_id = ident["delete_log"]
            row = db.query(getattr(models, model_name)).filter_by(id=log_id).first()
            if row is not None:
                user = db.query(models.User).filter_by(id=row.user_id).first()
        elif "user_id" in ident:
            user = db.query(models.User).filter_by(id=ident["user_id"]).first()
            if user is None:
                user = models.User(id=ident["user_id"], name="Legacy Test", email=f"legacy{ident['user_id']}@test.local")
        elif "email" in ident:
            user = db.query(models.User).filter_by(email=ident["email"].lower()).first()
            if user is None:
                user = models.User(name="Legacy Test", email=ident["email"].lower())
        if user is None:
            user = db.query(models.User).order_by(models.User.id).first()
            if user is None:
                user = models.User(id=1, name="Legacy Test", email="legacy1@test.local")
        if user.id is None or user not in db:
            db.add(user)
            db.commit()
            db.refresh(user)
        return user.id, user.email
    finally:
        if gen is not None:
            try:
                next(gen)
            except StopIteration:
                pass


@pytest.fixture(autouse=True)
def _legacy_auto_auth(request, monkeypatch):
    if getattr(request.module, "NO_LEGACY_AUTH", False) or request.module.__name__.endswith("test_auth_contract"):
        yield
        return
    original = _TestClient.request

    def patched(self, method, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        path = urllib.parse.urlsplit(str(url)).path
        if not any(k.lower() == "authorization" for k in headers) and not _PUBLIC_AUTH.search(path):
            uid, email = _resolve_user(_identity(method, url, kwargs))
            token = create_access_token({"sub": str(uid), "email": email or "legacy@test.local"})
            headers["Authorization"] = f"Bearer {token}"
            kwargs["headers"] = headers
        return original(self, method, url, **kwargs)

    monkeypatch.setattr(_TestClient, "request", patched)
    yield
