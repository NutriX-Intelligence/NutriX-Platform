from dataclasses import dataclass
from typing import List, Optional
import re
from gateway.config import MS1_CV_URL, MS2_LLM_URL, MS3_USER_URL, MS4_AGENTS_URL

@dataclass
class RouteConfig:
    methods: List[str]
    path_pattern: str
    target: str
    timeout: int
    auth_type: str

ROUTES = [
    RouteConfig(["POST"], r"^/api/v1/ingest/weight-frame$", MS1_CV_URL, 60, "device-token"),
    RouteConfig(["GET"], r"^/api/v1/barcode/.*$", MS1_CV_URL, 15, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/ocr/upload$", MS1_CV_URL, 30, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/hitl/confirm$", MS1_CV_URL, 30, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/auth/register$", MS3_USER_URL, 10, "public"),
    RouteConfig(["POST"], r"^/api/v1/auth/login$", MS3_USER_URL, 10, "public"),
    RouteConfig(["POST"], r"^/api/v1/auth/google$", MS3_USER_URL, 10, "public"),
    RouteConfig(["GET"], r"^/api/v1/auth/me$", MS3_USER_URL, 10, "jwt"),
    RouteConfig(["GET", "PUT"], r"^/api/v1/users/[^/]+$", MS3_USER_URL, 10, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/users/[^/]+/preferences$", MS3_USER_URL, 10, "jwt"),
    RouteConfig(["GET"], r"^/api/v1/user/daily-summary$", MS3_USER_URL, 5, "jwt"),
    RouteConfig(["GET"], r"^/api/v1/user/history$", MS3_USER_URL, 10, "jwt"),
    RouteConfig(["GET"], r"^/api/v1/user/targets$", MS3_USER_URL, 10, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/recipes/recommend$", MS3_USER_URL, 15, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/recipes/generate-instructions$", MS3_USER_URL, 30, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/barcode/alternatives$", MS3_USER_URL, 15, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/classify$", MS3_USER_URL, 10, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/meal-logs$", MS3_USER_URL, 10, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/meal-plans/generate$", MS3_USER_URL, 30, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/ai/coach$", MS3_USER_URL, 60, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/agent/query$", MS4_AGENTS_URL, 60, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/llm/lookup$", MS2_LLM_URL, 15, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/llm/vision-infer$", MS2_LLM_URL, 30, "jwt"),
]

def get_route_config(method: str, path: str) -> Optional[RouteConfig]:
    for route in ROUTES:
        if method in route.methods and re.match(route.path_pattern, path):
            return route
    return None
