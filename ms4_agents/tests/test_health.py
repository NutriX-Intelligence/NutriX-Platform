from fastapi.testclient import TestClient
from ms4_agents.main import app

client = TestClient(app)

def test_ms4_agents_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["ok", "healthy", "degraded"]
    assert response.json()["service"] == "ms4_agents"
