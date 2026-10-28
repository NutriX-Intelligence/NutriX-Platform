"""
MS3 test configuration.

The ported MS3 tests create/drop tables and write rows, so they must NEVER run against the
development Postgres. DATABASE_URL is forced to a throw-away SQLite file *before* shared.db is
imported, and a session fixture refuses to run if that did not take effect (for example because
another service's tests imported shared.db first). Run them on their own:

    PYTHONPATH=. pytest ms3_user/tests -v
"""
import os
import tempfile

# ── must happen before anything imports shared.db ───────────────────────────
os.environ["ENV"] = "dev"
os.environ.setdefault("JWT_SECRET_KEY", "ms3-test-secret")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), f"nutrix_ms3_tests_{os.getpid()}.db")
# unreachable on purpose: the Redis helpers then use their in-memory fallback and can never touch the dev cache
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
os.environ["GEMINI_API_KEY"] = ""
os.environ["AI_LOCAL_FALLBACK"] = "false"  # tests that need the local model switch it on explicitly

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _jsonb_as_json_on_sqlite(type_, compiler, **kw):
    return "JSON"


from shared import db as shared_db  # noqa: E402
from shared import models  # noqa: E402,F401  (registers every table on Base)


@pytest.fixture(scope="session", autouse=True)
def _isolated_sqlite_database():
    url = str(shared_db.engine.url)
    if not url.startswith("sqlite"):
        pytest.exit(
            f"Refusing to run MS3 tests against {url!r}. Run `pytest ms3_user/tests` on its own "
            "so DATABASE_URL points at the throw-away SQLite database.",
            returncode=2,
        )
    shared_db.Base.metadata.create_all(bind=shared_db.engine)
    yield
    shared_db.Base.metadata.drop_all(bind=shared_db.engine)
    try:
        os.remove(url.replace("sqlite:///", "", 1))
    except OSError:
        pass


def make_token(user_id: int, email: str = "user@example.com") -> str:
    """A valid MS3/gateway token for `user_id` (sub = numeric id)."""
    from ms3_user.services.auth_service import create_access_token
    return create_access_token({"sub": str(user_id), "email": email})


def auth_headers(user_id: int = 1, email: str = "user@example.com") -> dict:
    return {"Authorization": f"Bearer {make_token(user_id, email)}"}

from ms3_user.tests._legacy_auth import _legacy_auto_auth  # noqa: E402,F401  (autouse; see that module)
