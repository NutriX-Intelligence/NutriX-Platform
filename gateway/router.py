from dataclasses import dataclass
from typing import List, Optional
import os
import re
from gateway.config import MS1_CV_URL, MS2_LLM_URL, MS3_USER_URL, MS4_AGENTS_URL


@dataclass
class RouteConfig:
    methods: List[str]
    path_pattern: str
    target: str
    timeout: int
    auth_type: str


ALL_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]

# The existing app/dashboard call MS3 at its old, unprefixed paths. MS3 serves both spellings
# (see ms3_user/routing.py); switch the legacy ones off with ENABLE_LEGACY_ROUTES=false.
LEGACY_ENABLED = os.getenv("ENABLE_LEGACY_ROUTES", "true").strip().lower() in ("1", "true", "yes", "on")

# Namespaces MS3 owns under /api/v1
_MS3_NS = (
    r"auth|users|user|meal-logs|water-logs|weight-logs|recipes|foods|meal-plans|fast-food|classify|"
    r"barcode|ocr|homely|homely-meals|analytics|search-history|settings"
)
# ...and the same names at their legacy locations
_MS3_LEGACY_API_NS = (
    r"auth|meal-logs|water-logs|weight-logs|recipes|fast-food|classify|barcode|ocr|homely|homely-meals|"
    r"analytics|search-history|settings"
)

# NOTE: first match wins, so specific rules (timeouts, public auth) come before the generic ones.
ROUTES: List[RouteConfig] = [
    # ── MS1: scale ingestion ────────────────────────────────────────────────
    RouteConfig(["POST"], r"^/api/v1/ingest/weight-frame$", MS1_CV_URL, 60, "device-token"),
    RouteConfig(["GET"],  r"^/api/v1/ingest/result/[^/]+$", MS1_CV_URL, 10, "device-token"),
    RouteConfig(["POST"], r"^/api/v1/hitl/confirm$", MS1_CV_URL, 30, "jwt"),

    # ── MS3: public authentication ──────────────────────────────────────────
    RouteConfig(["POST"], r"^/api/v1/auth/(register|login|google|reset-password)$", MS3_USER_URL, 10, "public"),

    # ── MS3: AI features (Gemini; can be slow) ──────────────────────────────
    RouteConfig(["POST"], r"^/api/v1/ai/.+$", MS3_USER_URL, 90, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/recipes/generate-instructions$", MS3_USER_URL, 90, "jwt"),

    # ── MS3: barcode / OCR / meal plans (external lookups, OR-Tools) ────────
    RouteConfig(["GET", "POST"], r"^/api/v1/(barcode|ocr)(/.*)?$", MS3_USER_URL, 45, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/meal-plans/generate$", MS3_USER_URL, 45, "jwt"),

    # ── MS3: live dashboard stream (SSE; heartbeats every 15 s keep the read timeout from firing) ──
    RouteConfig(["GET"], r"^/api/v1/user/stream$", MS3_USER_URL, 120, "jwt"),

    # ── MS3: everything else under its namespaces ───────────────────────────
    RouteConfig(ALL_METHODS, rf"^/api/v1/({_MS3_NS})(/.*)?$", MS3_USER_URL, 30, "jwt"),

    # ── MS2: internal LLM endpoints (exposed for authenticated testing) ─────
    RouteConfig(["POST"], r"^/api/v1/llm/lookup$", MS2_LLM_URL, 15, "jwt"),
    RouteConfig(["POST"], r"^/api/v1/llm/vision-infer$", MS2_LLM_URL, 30, "jwt"),

    # ── MS4: agents ─────────────────────────────────────────────────────────
    RouteConfig(["POST"], r"^/api/v1/agent/query$", MS4_AGENTS_URL, 60, "jwt"),
]

if LEGACY_ENABLED:
    ROUTES += [
        RouteConfig(["POST"], r"^/api/auth/(register|login|google|reset-password)$", MS3_USER_URL, 10, "public"),
        RouteConfig(["POST"], r"^/api/(ai/.+|recipes/generate-instructions)$", MS3_USER_URL, 90, "jwt"),
        RouteConfig(["GET", "POST"], r"^/api/(barcode|ocr)(/.*)?$", MS3_USER_URL, 45, "jwt"),
        RouteConfig(["POST"], r"^/generate-meal-plan$", MS3_USER_URL, 45, "jwt"),
        RouteConfig(ALL_METHODS, rf"^/api/({_MS3_LEGACY_API_NS})(/.*)?$", MS3_USER_URL, 30, "jwt"),
        RouteConfig(ALL_METHODS, r"^/(users|recipes)/.+$", MS3_USER_URL, 30, "jwt"),
        RouteConfig(["POST"], r"^/(calculate-profile|recommend-foods|track-weight)$", MS3_USER_URL, 30, "jwt"),
    ]


def get_route_config(method: str, path: str) -> Optional[RouteConfig]:
    for route in ROUTES:
        if method in route.methods and re.match(route.path_pattern, path):
            return route
    return None
