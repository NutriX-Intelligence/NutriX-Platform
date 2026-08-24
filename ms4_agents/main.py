from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from shared.db import get_db
from shared.health import check_health

app = FastAPI(title="NutriX MS4 Clinical Guardian & Multi-Agent Engine", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return check_health(service_name="ms4_agents", db=db, include_redis=True, version="1.0.0")
