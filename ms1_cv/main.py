from fastapi import FastAPI

app = FastAPI(title="NutriX MS1 CV & Ingestion Service", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ms1_cv"}
