from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from shared.db import get_db
from shared.health import check_health

app = FastAPI(title="NutriX MS1 CV & Ingestion Service", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return check_health(service_name="ms1_cv", db=db, include_redis=True, version="1.0.0")
