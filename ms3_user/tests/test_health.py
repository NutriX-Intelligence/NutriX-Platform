from fastapi.testclient import TestClient
from ms3_user.main import app

client = TestClient(app)

def test_ms3_user_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "ms3_user"
