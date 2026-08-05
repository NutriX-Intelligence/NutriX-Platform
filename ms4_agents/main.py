from fastapi import FastAPI

app = FastAPI(title="NutriX MS4 Multi-Agent System (MAS)", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ms4_agents"}
