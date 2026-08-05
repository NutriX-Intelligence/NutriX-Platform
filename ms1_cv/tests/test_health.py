from fastapi.testclient import TestClient
from ms1_cv.main import app

client = TestClient(app)

def test_ms1_cv_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ms1_cv"
