from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from shared.db import get_db
from shared.health import check_health
from ms3_user.services.macro_listener import start_macro_listener_thread, stop_macro_listener_thread

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start PostgreSQL NOTIFY listener for real-time Redis sync
    start_macro_listener_thread()
    yield
    # Shutdown: cleanly terminate listener thread
    stop_macro_listener_thread()

app = FastAPI(title="NutriX MS3 User & Analytics Service", version="1.0.0", lifespan=lifespan)

@app.get("/")
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return check_health(service_name="ms3_user", db=db, include_redis=True, version="1.0.0")
