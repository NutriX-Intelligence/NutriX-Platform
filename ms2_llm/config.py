import os
from pathlib import Path

# Auto-load root .env if present (same pattern as gateway/config.py)
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# Local snapshot dir of Qwen3-VL-2B-Instruct (falls back to the HF hub id)
VLM_MODEL_PATH = os.getenv("VLM_MODEL_PATH", "Qwen/Qwen3-VL-2B-Instruct")
VLM_MAX_NEW_TOKENS = int(os.getenv("VLM_MAX_NEW_TOKENS", "128"))
VLM_MAX_PIXELS = int(os.getenv("VLM_MAX_PIXELS", str(480 * 640)))
# true: load once at startup and stay resident. false: load per call, free afterwards.
VLM_KEEP_LOADED = _bool("VLM_KEEP_LOADED", True)
# Set false to start MS2 without touching the GPU (dev/CI).
VLM_AUTOLOAD = _bool("VLM_AUTOLOAD", True)
# How long cached registry prompts stay valid
PROMPT_CACHE_TTL_S = int(os.getenv("PROMPT_CACHE_TTL_S", "60"))
