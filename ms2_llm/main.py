from fastapi import FastAPI

app = FastAPI(title="NutriX MS2 LLM Nutrition & Vision Service", version="1.0.0")

@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ms2_llm"}
