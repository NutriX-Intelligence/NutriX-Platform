from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "gateway"}

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
