import os
from pathlib import Path

# Auto-load root .env if present
_base_dir = Path(__file__).resolve().parent.parent
_env_file = _base_dir / ".env"
if _env_file.exists():
    with open(_env_file, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

def _clean_service_url(env_var: str, default: str) -> str:
    val = os.getenv(env_var, default)
    if not os.path.exists("/.dockerenv"):
        for host in ["ms1-cv", "ms2-llm", "ms3-user", "ms4-agents"]:
            val = val.replace(f"//{host}:", "//localhost:")
    return val

MS1_CV_URL     = _clean_service_url("MS1_CV_URL",     "http://localhost:8001")
MS2_LLM_URL    = _clean_service_url("MS2_LLM_URL",    "http://localhost:8003")
MS3_USER_URL   = _clean_service_url("MS3_USER_URL",   "http://localhost:8002")
MS4_AGENTS_URL = _clean_service_url("MS4_AGENTS_URL", "http://localhost:8004")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-insecure-secret")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM",  "HS256")
DEVICE_TOKEN   = os.getenv("DEVICE_TOKEN",   "NutriX_ESP32_SECURE_TOKEN")

