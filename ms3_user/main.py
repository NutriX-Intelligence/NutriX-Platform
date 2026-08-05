from fastapi import FastAPI
# TO BE PUT BY FGLORD
app = FastAPI(title="NutriX MS3 User & Analytics Service", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ms3_user"}
