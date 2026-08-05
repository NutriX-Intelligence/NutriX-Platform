from fastapi.testclient import TestClient
from ms2_llm.main import app

client = TestClient(app)

def test_ms2_llm_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ms2_llm"
