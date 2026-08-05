from fastapi import FastAPI

app = FastAPI(title="NutriX API Gateway", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "gateway"}
