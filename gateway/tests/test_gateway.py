import pytest
from fastapi.testclient import TestClient
from gateway.main import app
from gateway.config import JWT_SECRET_KEY, JWT_ALGORITHM, DEVICE_TOKEN
from jose import jwt
import time
import httpx
from unittest.mock import patch, AsyncMock

def create_mock_jwt(user_id="user_123", expired=False):
    exp = int(time.time()) - 3600 if expired else int(time.time()) + 3600
    payload = {"sub": user_id, "exp": exp}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def test_health_check():
    with TestClient(app) as test_client:
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

def test_root():
    with TestClient(app) as test_client:
        response = test_client.get("/")
        assert response.status_code == 200
        assert "NutriX API Gateway" in response.json()["message"]

@pytest.fixture
def mock_httpx_send():
    with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
        class MockResponse:
            def __init__(self):
                self.status_code = 200
                self.headers = httpx.Headers({"Content-Type": "application/json"})
            async def aiter_raw(self):
                yield b'{"mock": "response"}'

        mock_send.return_value = MockResponse()
        yield mock_send

def test_public_route_proxy(mock_httpx_send):
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/auth/login", json={"email": "test@test.com"})
        assert response.status_code == 200
        assert response.json() == {"mock": "response"}
        mock_httpx_send.assert_called_once()

def test_jwt_route_missing_token():
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/user/daily-summary")
        assert response.status_code == 401
        assert "Missing or invalid Authorization header" in response.json()["detail"]

def test_jwt_route_valid_token(mock_httpx_send):
    token = create_mock_jwt()
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/user/daily-summary", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == {"mock": "response"}

def test_device_token_route_missing_token():
    with TestClient(app) as test_client:
        response = test_client.post("/api/v1/ingest/weight-frame")
        assert response.status_code == 401
        assert "Missing Device-Token header" in response.json()["detail"]

def test_device_token_route_valid_token(mock_httpx_send):
    with TestClient(app) as test_client:
        headers = {
            "Device-Token": DEVICE_TOKEN,
            "User-ID": "test_user_1"
        }
        response = test_client.post("/api/v1/ingest/weight-frame", headers=headers, json={"weight": 100})
        assert response.status_code == 200
        assert response.json() == {"mock": "response"}
