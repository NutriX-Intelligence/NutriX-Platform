# Phase 2 — API Gateway (Port 8000)

> **Goal:** A hardened, production-ready API Gateway that is the **single authenticated front door** for
> the entire NutriX platform. Every request from the ESP32 scale, Flutter app, and internal callers must
> pass through Port 8000. This phase produces a fully functional, containerised gateway with JWT and
> Device-Token auth, async reverse-proxy routing to all 4 microservices, structured request logging,
> and complete Dockerization — without touching any microservice internals.

**Phase Status:** Not Started
**Depends On:** Phase 1 (Complete)
**Blocks:** Phase 3, 5, 6, 7 (all services expose ports only inside Docker network)

---

## Context and Architecture Alignment

From MASTER_ARCHITECTURE.md Layer 2:

The gateway is deliberately NOT a BFF (Backend for Frontend) and performs ZERO business logic.
It is a pure security + routing layer. All computation lives in microservices.

External World              |  Internal Docker Network (nutrix-net)
----------------------------+------------------------------------------
ESP32 Scale (Device-Token)  |
Flutter App (JWT Bearer)    +-- gateway:8000 --> ms1-cv:8001    (scale uploads)
Any REST Client (JWT)       |                --> ms3-user:8002  (user/auth APIs)
                            |                --> ms2-llm:8003   (LLM internal)
                            |                --> ms4-agents:8004 (agent queries)

### What Phase 2 Is NOT

- No business logic (no DB reads inside gateway code)
- No per-user authorisation checks (that is MS3 job)
- No response transformation or aggregation
- No MS3/MS1 endpoint implementation (those are Phase 3 and 5)

---

## Delivery Checklist

### 2.1 Async Reverse Proxy Engine (gateway/proxy.py)

The core proxy must stream multipart payloads without buffering the entire body in memory.
This is critical for scale uploads (JPEG frames can be several hundred KB).

Implementation:
- Use httpx.AsyncClient with follow_redirects=True and a configurable per-route timeout.
- Forward the original request headers (minus host) to the upstream.
- Add X-Forwarded-For and X-Request-ID (uuid4) headers to every upstream call.
- For POST /v1/ingest/weight-frame use a 60-second timeout (YOLO inference is slow).
- For all other routes, apply a 30-second timeout by default.
- On upstream timeout or 5xx: return 503 Service Unavailable with JSON error body.
- On upstream connection refused: return 502 Bad Gateway.

File: gateway/proxy.py

---

### 2.2 JWT Bearer Token Middleware (gateway/middleware/auth.py)

Validates JWT tokens for Flutter app requests on all routes except the whitelist.

JWT Specification:
- Algorithm: HS256
- Secret: JWT_SECRET_KEY env var
- Claims required: sub (user_id as string), exp (expiry timestamp)
- Header format: Authorization: Bearer <token>

Implementation:
- Use python-jose[cryptography] (already in gateway/requirements.txt).
- Implement as per-route dependency injection (not global middleware).
- On valid token: inject X-User-ID: <sub> header into the forwarded request.
- On invalid/expired token: immediately return 401 Unauthorized.

Public Routes (no JWT required):
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/google
  GET  /health
  GET  /

Device-Token Routes (JWT excluded, Device-Token required instead):
  POST /api/v1/ingest/weight-frame

File: gateway/middleware/auth.py

---

### 2.3 Device-Token Middleware (gateway/middleware/device_auth.py)

Authenticates physical ESP32-S3 scale hardware using a shared pre-configured secret token.

Device-Token Specification:
- Header name: Device-Token
- Value from env: DEVICE_TOKEN (example: NutriX_ESP32_SECURE_TOKEN_9921)
- Secondary header: User-ID (the user whose scale is reporting)

Implementation:
- Applied only to POST /api/v1/ingest/weight-frame.
- Validates Device-Token header via constant-time comparison (hmac.compare_digest).
- If User-ID header is missing: return 400 Bad Request.
- If token missing or mismatched: return 401 Unauthorized.
- On success: inject X-User-ID into forwarded request.

File: gateway/middleware/device_auth.py

---

### 2.4 Route Table and Request Router (gateway/router.py)

Maps every incoming URL path to the correct upstream microservice URL, timeout, and auth type.

Complete Route Table (all 23 routes from MASTER_ARCHITECTURE.md with standardized `/api/v1/` convention):

Auth Type    | Method    | Path Pattern                             | Upstream        | Timeout
-------------|-----------|------------------------------------------|-----------------|--------
device-token | POST      | /api/v1/ingest/weight-frame              | MS1_CV_URL      | 60s
jwt          | GET       | /api/v1/barcode/{barcode}               | MS1_CV_URL      | 15s
jwt          | POST      | /api/v1/ocr/upload                      | MS1_CV_URL      | 30s
jwt          | POST      | /api/v1/hitl/confirm                    | MS1_CV_URL      | 30s
public       | POST      | /api/v1/auth/register                   | MS3_USER_URL    | 10s
public       | POST      | /api/v1/auth/login                      | MS3_USER_URL    | 10s
public       | POST      | /api/v1/auth/google                     | MS3_USER_URL    | 10s
jwt          | GET       | /api/v1/auth/me                         | MS3_USER_URL    | 10s
jwt          | GET, PUT  | /api/v1/users/{id}                      | MS3_USER_URL    | 10s
jwt          | POST      | /api/v1/users/{id}/preferences          | MS3_USER_URL    | 10s
jwt          | GET       | /api/v1/user/daily-summary               | MS3_USER_URL    | 5s
jwt          | GET       | /api/v1/user/history                     | MS3_USER_URL    | 10s
jwt          | GET       | /api/v1/user/targets                     | MS3_USER_URL    | 10s
jwt          | POST      | /api/v1/recipes/recommend               | MS3_USER_URL    | 15s
jwt          | POST      | /api/v1/recipes/generate-instructions   | MS3_USER_URL    | 30s
jwt          | POST      | /api/v1/barcode/alternatives            | MS3_USER_URL    | 15s
jwt          | POST      | /api/v1/classify                        | MS3_USER_URL    | 10s
jwt          | POST      | /api/v1/meal-logs                       | MS3_USER_URL    | 10s
jwt          | POST      | /api/v1/meal-plans/generate             | MS3_USER_URL    | 30s
jwt          | POST      | /api/v1/ai/coach                        | MS3_USER_URL    | 60s
jwt          | POST      | /api/v1/agent/query                     | MS4_AGENTS_URL  | 60s
jwt          | POST      | /api/v1/llm/lookup                       | MS2_LLM_URL     | 15s
jwt          | POST      | /api/v1/llm/vision-infer                 | MS2_LLM_URL     | 30s

Implementation notes:
- Use a RouteConfig dataclass with path_pattern, methods, target, timeout, auth_type fields.
- Use prefix matching so /api/v1/users/42 matches the /api/v1/users/{id} pattern.
- Router raises 404 JSON response on no match.

File: gateway/router.py

---

### 2.5 Request Logging Middleware (gateway/middleware/logging_mw.py)

Structured JSON request log for every inbound request and upstream response.

Log Schema per request:
```json
{
  "timestamp": "2026-08-24T18:30:00.000Z",
  "request_id": "a3f1-...",
  "method": "POST",
  "path": "/api/v1/ingest/weight-frame",
  "client_ip": "192.168.1.55",
  "user_id": "42",
  "target_service": "ms1-cv:8001",
  "status_code": 200,
  "duration_ms": 312.4,
  "auth_type": "device-token"
}
```

Implementation:
- FastAPI @app.middleware("http") runs for every request.
- Capture time.perf_counter() before and after await call_next(request).
- Log with Python standard logging module at INFO level using json.dumps.
- Sensitive headers (Authorization, Device-Token) must never appear in logs.

File: gateway/middleware/logging_mw.py

---

### 2.6 Main App Assembly (gateway/main.py)

Wire all pieces together. The current stub (10 lines) gets replaced entirely.

Key design decisions:
- Single httpx.AsyncClient created at startup (shared connection pool) and closed at shutdown.
- Logging middleware registered globally via app.add_middleware.
- Auth applied per-route via the catch-all route handler that classifies auth type from the route
  table before calling the proxy.
- Catch-all route: @app.api_route("/{path:path}", methods=["GET","POST","PUT","DELETE","PATCH"]).
- /health and / remain standalone routes (not proxied).
- Log all upstream service URLs at startup for observability.

File: gateway/main.py

---

### 2.7 Config and Environment (gateway/config.py)

Single config module pulling all env vars with safe local defaults.

MS1_CV_URL     = os.getenv("MS1_CV_URL",     "http://localhost:8001")
MS2_LLM_URL    = os.getenv("MS2_LLM_URL",    "http://localhost:8003")
MS3_USER_URL   = os.getenv("MS3_USER_URL",   "http://localhost:8002")
MS4_AGENTS_URL = os.getenv("MS4_AGENTS_URL", "http://localhost:8004")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-insecure-secret")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM",  "HS256")
DEVICE_TOKEN   = os.getenv("DEVICE_TOKEN",   "NutriX_ESP32_SECURE_TOKEN")

Defaults point to localhost for local dev (outside Docker). Docker Compose .env overrides
these to container names automatically.

File: gateway/config.py

---

### 2.8 Dockerfile Hardening (gateway/Dockerfile)

Changes:
1. Add non-root user nutrix for Docker security.
2. Add HEALTHCHECK instruction so Docker Compose knows when gateway is ready.
3. Pin uvicorn to 1 worker for dev simplicity (increase in Phase 9).

FROM python:3.11-slim
RUN adduser --disabled-password --gecos '' nutrix
WORKDIR /app
COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gateway/ ./gateway/
COPY shared/ ./shared/
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
USER nutrix
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

File: gateway/Dockerfile

---

### 2.9 docker-compose.yml Gateway depends_on

The gateway should not start until Postgres and Redis report healthy.

Add to gateway service in docker-compose.yml:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy

File: docker-compose.yml

---

### 2.10 Gateway Test Suite (gateway/tests/test_gateway.py)

All 15 tests must run in CI without a live network (all upstreams mocked via respx).

Test Name                                | Description
-----------------------------------------|-----------------------------------------------------
test_health_endpoint                     | GET /health returns 200 and valid status field
test_jwt_missing_returns_401             | Protected route without any token returns 401
test_jwt_invalid_returns_401             | Protected route with garbage token returns 401
test_jwt_expired_returns_401             | Protected route with expired token returns 401
test_jwt_valid_proxies_request           | Valid token: mock upstream called, response forwarded
test_device_token_valid_proxies          | Valid Device-Token + User-ID: upstream called
test_device_token_missing_returns_401    | Missing Device-Token header returns 401
test_device_token_missing_userid_returns_400 | Token OK but no User-ID returns 400
test_public_route_no_auth               | POST /api/auth/login proxies without auth header
test_unknown_route_returns_404           | Unknown path returns 404 JSON
test_upstream_timeout_returns_503        | Mocked upstream hangs returns 503
test_upstream_refused_returns_502        | Mocked upstream refuses returns 502
test_x_user_id_injected_from_jwt        | JWT sub claim injected as X-User-ID in upstream call
test_x_request_id_injected              | Every proxied call has X-Request-ID header
test_sensitive_headers_not_logged        | Authorization absent from log output

Mock library: respx>=0.21.0 cleanly intercepts httpx calls without monkeypatching.

Files:
- gateway/tests/test_gateway.py
- gateway/requirements.txt (add respx>=0.21.0)

---

## File Change Summary

Action    | File                                  | Purpose
----------|---------------------------------------|-------------------------------------------
[NEW]     | gateway/config.py                     | All env-var config in one place
[NEW]     | gateway/proxy.py                      | Async httpx reverse proxy engine
[NEW]     | gateway/router.py                     | Route table and path-matching logic
[NEW]     | gateway/middleware/__init__.py        | Package marker
[NEW]     | gateway/middleware/auth.py            | JWT Bearer validation
[NEW]     | gateway/middleware/device_auth.py     | Device-Token validation for ESP32
[NEW]     | gateway/middleware/logging_mw.py      | Structured JSON request/response logger
[MODIFY]  | gateway/main.py                       | Wire all middleware and proxy catch-all
[MODIFY]  | gateway/Dockerfile                    | Non-root user, HEALTHCHECK, workers=1
[MODIFY]  | gateway/requirements.txt              | Add respx>=0.21.0 for tests
[MODIFY]  | docker-compose.yml                    | Add gateway depends_on postgres + redis
[NEW]     | gateway/tests/test_gateway.py         | Full gateway test suite (15 tests, mocked)

---

## Implementation Order

1. gateway/config.py                   (no deps)
2. gateway/router.py                   (needs config)
3. gateway/proxy.py                    (needs config)
4. gateway/middleware/auth.py          (needs config)
5. gateway/middleware/device_auth.py   (needs config)
6. gateway/middleware/logging_mw.py    (no deps)
7. gateway/main.py                     (needs all above)
8. gateway/Dockerfile                  (needs working main.py)
9. docker-compose.yml                  (needs Dockerfile)
10. gateway/tests/test_gateway.py      (needs main.py)

---

## Verification Plan

### Local Dev (without Docker)

# 1. Start only infra containers
docker-compose up postgres redis -d

# 2. Run gateway directly
PYTHONPATH=. uvicorn gateway.main:app --reload --port 8000

# 3. Health check
curl http://localhost:8000/health
# Expected: {"status": "healthy", "service": "gateway", ...}

# 4. Generate a test JWT (run helper script for easy copy-paste)
python gateway/generate_token.py

# 5. Test protected route (Copy and run the curl command outputted from step 4)
# Expected: HTTP/1.1 502 Bad Gateway ({"detail":"Bad Gateway (Connection Refused)"})

# 6. Test auth rejection (no token provided)
curl -i http://localhost:8000/api/v1/user/daily-summary
# Expected: HTTP/1.1 401 Unauthorized ({"detail":"Missing or invalid Authorization header"})

# 7. Test Device-Token (MS1 not up -> 502 Bad Gateway, proving device auth passed)
curl -i -X POST http://localhost:8000/api/v1/ingest/weight-frame -H "Device-Token: NutriX_ESP32_SECURE_TOKEN" -H "User-ID: 1" -F "weight=200.5"
# Expected: HTTP/1.1 502 Bad Gateway ({"detail":"Bad Gateway (Connection Refused)"})

# 8. Run CI test suite
pytest gateway/tests/ -v
# Expected: 15 passed

### Docker Compose Verification

docker-compose up gateway postgres redis -d
curl http://localhost:8000/health
docker-compose logs gateway   # check structured JSON logs

---

## Design Decisions Log

Decision                   | Choice                    | Rationale
---------------------------|---------------------------|-----------------------------------------
Auth implementation        | Per-route classification  | Avoids global middleware ordering issues
Proxy library              | httpx.AsyncClient         | Already in deps; async; streaming support
Token validation           | python-jose HS256         | Already in deps; matches Flutter JWT
Device-Token comparison    | hmac.compare_digest       | Prevents timing attacks
Logging format             | Structured JSON stdout    | Docker log drivers and cloud logging ready
Gateway DB connection      | None                      | Routing-only; SQLAlchemy would be dead weight
Service discovery          | Env var URL config        | Portable across local/Docker/cloud
Test mocking               | respx for httpx           | CI-safe; no monkeypatching
Uvicorn workers            | 1 for now                 | Dev simplicity; scale in Phase 9
