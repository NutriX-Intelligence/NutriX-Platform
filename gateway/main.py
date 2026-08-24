from fastapi import FastAPI
from shared.health import check_health

app = FastAPI(title="NutriX API Gateway", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check():
    return check_health(service_name="gateway", db=None, include_redis=True, version="1.0.0")
