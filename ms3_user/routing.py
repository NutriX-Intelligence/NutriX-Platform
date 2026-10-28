"""
Dual-path routing for MS3.

Every handler is declared once with its *legacy* path (the one the existing app/dashboard calls).
`DualRouter` registers it under the canonical gateway path (`/api/v1/...`) and, while
ENABLE_LEGACY_ROUTES is on, also under the legacy path (hidden from OpenAPI).
"""
import os

from fastapi import APIRouter

LEGACY_ENABLED = os.getenv("ENABLE_LEGACY_ROUTES", "true").strip().lower() in ("1", "true", "yes", "on")

# legacy path -> canonical path (without the /api/v1 prefix) where the default rule is not enough
CANONICAL_OVERRIDES = {
    "/api/ocr": "/ocr/upload",
    "/generate-meal-plan": "/meal-plans/generate",
    "/track-weight": "/weight-logs",
    "/recommend-foods": "/foods/recommend",
    "/calculate-profile": "/user/profile",
}


def canonical_path(path: str) -> str:
    """Default rule: `/api/x/y` -> `/api/v1/x/y`, `/x/y` -> `/api/v1/x/y`."""
    if path in CANONICAL_OVERRIDES:
        return "/api/v1" + CANONICAL_OVERRIDES[path]
    rel = path[len("/api"):] if path.startswith("/api/") else path
    return "/api/v1" + rel


class DualRouter:
    def __init__(self, router: APIRouter):
        self.router = router

    def _route(self, methods, path, **kwargs):
        def decorator(fn):
            canonical = canonical_path(path)
            self.router.add_api_route(canonical, fn, methods=methods, **kwargs)
            if LEGACY_ENABLED and canonical != path:
                legacy_kwargs = dict(kwargs)
                legacy_kwargs["include_in_schema"] = False
                self.router.add_api_route(path, fn, methods=methods, **legacy_kwargs)
            return fn
        return decorator

    def get(self, path, **kwargs):
        return self._route(["GET"], path, **kwargs)

    def post(self, path, **kwargs):
        return self._route(["POST"], path, **kwargs)

    def put(self, path, **kwargs):
        return self._route(["PUT"], path, **kwargs)

    def delete(self, path, **kwargs):
        return self._route(["DELETE"], path, **kwargs)
