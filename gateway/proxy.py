import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
import uuid

# A shared async client created at startup and closed at shutdown.
client: httpx.AsyncClient = None

async def proxy_request(request: Request, target_url: str, timeout: int, user_id: str = None) -> StreamingResponse | JSONResponse:
    url = f"{target_url}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
        
    headers = dict(request.headers)
    headers.pop("host", None)
    
    headers["X-Forwarded-For"] = request.client.host if request.client else "127.0.0.1"
    if "x-request-id" not in {k.lower(): v for k, v in headers.items()}:
        headers["X-Request-ID"] = str(uuid.uuid4())
    if user_id:
        headers["X-User-ID"] = str(user_id)
        
    try:
        req = client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=request.stream(),
            timeout=timeout
        )
        response = await client.send(req, stream=True)
        
        return StreamingResponse(
            response.aiter_raw(),
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")}
        )
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"detail": "Service Unavailable (Timeout)"})
    except (httpx.ConnectError, httpx.NetworkError):
        return JSONResponse(status_code=502, content={"detail": "Bad Gateway (Connection Refused)"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"Internal Proxy Error: {str(e)}"})
