"""
NutriX MS3: User & Analytics Service (port 8002).

* All routes live in `ms3_user.routes` and are served under `/api/v1/...` plus (while
  ENABLE_LEGACY_ROUTES=true) the legacy paths the existing app/dashboard call.
* Auth: Bearer JWT (sub = user id), see `ms3_user.deps`.
* The Postgres `macro_update` NOTIFY listener keeps the Redis daily-macro cache in sync.
"""
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from shared.db import get_db
from shared.health import check_health
from ms3_user.routes import api_router, public_router
from ms3_user.services.macro_listener import start_macro_listener_thread, stop_macro_listener_thread

ENV = os.getenv("ENV", "prod").strip().lower()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: PostgreSQL NOTIFY listener for real-time Redis sync
    start_macro_listener_thread()
    yield
    stop_macro_listener_thread()


app = FastAPI(
    title="NutriX MS3 User & Analytics Service",
    description="User accounts, profiles, logs, recipes, meal plans, fast food, barcode/OCR and AI coaching.",
    version="2.0.0",
    lifespan=lifespan,
)

_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Reuse the gateway's X-Request-ID (or create one) and echo it back."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    return response


@app.get("/")
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return check_health(service_name="ms3_user", db=db, include_redis=True, version="2.0.0")


app.include_router(public_router)
app.include_router(api_router)

if ENV == "dev":
    # The standalone web dashboard that shipped with MS3: handy as a test client (dev only, not routed by the gateway).
    _DEV_UI = Path(__file__).resolve().parent / "dev_ui" / "index.html"

    @app.get("/dev-ui", response_class=HTMLResponse, include_in_schema=False)
    def dev_ui():
        if not _DEV_UI.exists():
            return HTMLResponse("<h1>NutriX dev UI not found</h1>", status_code=404)
        html = _DEV_UI.read_text(encoding="utf-8")
        client_id = os.getenv("GOOGLE_CLIENT_ID", "").split(",")[0].strip()
        if client_id:
            html = html.replace(
                'data-client_id="984515824955-jjec804gresaml38o7eicr2cegklmqtt.apps.googleusercontent.com"',
                f'data-client_id="{client_id}"',
            )
        return HTMLResponse(html)
