from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from gateway.middleware.logging_mw import logging_middleware
from gateway.middleware.auth import verify_jwt_token
from gateway.middleware.device_auth import verify_device_token
from gateway.router import get_route_config
from gateway.proxy import proxy_request
import gateway.proxy as proxy
from gateway.config import MS1_CV_URL, MS2_LLM_URL, MS3_USER_URL, MS4_AGENTS_URL
import httpx
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger = logging.getLogger("gateway")
    logger.info("Initializing API Gateway...")
    logger.info(f"MS1 CV URL: {MS1_CV_URL}")
    logger.info(f"MS2 LLM URL: {MS2_LLM_URL}")
    logger.info(f"MS3 USER URL: {MS3_USER_URL}")
    logger.info(f"MS4 AGENTS URL: {MS4_AGENTS_URL}")
    # Initialize shared httpx AsyncClient
    proxy.client = httpx.AsyncClient(follow_redirects=True)
    yield
    if proxy.client:
        await proxy.client.aclose()

app = FastAPI(title="NutriX API Gateway", lifespan=lifespan)

# Register global logging middleware
app.middleware("http")(logging_middleware)

# CORS for browsers / Flutter web (comma separated origins, '*' = any)
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "gateway"}

@app.get("/health/all")
async def health_all():
    """Gateway + every downstream service in one call (used by the runbooks and monitoring)."""
    import asyncio
    services = {"ms1_cv": MS1_CV_URL, "ms2_llm": MS2_LLM_URL, "ms3_user": MS3_USER_URL, "ms4_agents": MS4_AGENTS_URL}

    async def probe(name: str, url: str):
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f"{url}/health")
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            return name, {"status": body.get("status", "ok" if r.status_code == 200 else "error"), "http": r.status_code}
        except Exception as e:
            return name, {"status": "down", "error": type(e).__name__}

    results = dict(await asyncio.gather(*(probe(n, u) for n, u in services.items())))
    down = [n for n, v in results.items() if v["status"] == "down"]
    return {"gateway": "healthy", "overall": "degraded" if down else "healthy", "services": results}


@app.get("/")
async def root():
    return {"message": "NutriX API Gateway"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all_proxy(request: Request, path: str):
    # Ensure path starts with /
    full_path = f"/{path}"
    
    route = get_route_config(request.method, full_path)
    if not route:
        return JSONResponse(status_code=404, content={"detail": f"Route not found: {request.method} {full_path}"})
        
    request.state.target_service = route.target
    request.state.auth_type = route.auth_type
    
    user_id = None
    
    try:
        if route.auth_type == "jwt":
            user_id = verify_jwt_token(request)
        elif route.auth_type == "device-token":
            user_id = verify_device_token(request)
    except Exception as e:
        if hasattr(e, "status_code"):
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        return JSONResponse(status_code=500, content={"detail": f"Auth error: {str(e)}"})
        
    if user_id:
        request.state.user_id = user_id
        
    return await proxy_request(request, route.target, route.timeout, user_id)
