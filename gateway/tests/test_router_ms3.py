"""Routing table checks for the MS3 integration (pure function tests, no network)."""
import pytest

from gateway.config import MS1_CV_URL, MS3_USER_URL
from gateway.router import get_route_config


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/v1/auth/register"), ("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/google"),
    ("POST", "/api/auth/login"), ("POST", "/api/auth/register"),
])
def test_auth_entrypoints_are_public_and_go_to_ms3(method, path):
    cfg = get_route_config(method, path)
    assert cfg and cfg.target == MS3_USER_URL and cfg.auth_type == "public"


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/auth/me"), ("GET", "/api/v1/user/daily-summary"), ("GET", "/api/v1/user/history"),
    ("POST", "/api/v1/meal-logs"), ("DELETE", "/api/v1/meal-logs/4"), ("GET", "/api/v1/water-logs/today/1"),
    ("POST", "/api/v1/weight-logs"), ("GET", "/api/v1/recipes/top"), ("POST", "/api/v1/recipes/recommend"),
    ("POST", "/api/v1/meal-plans/generate"), ("GET", "/api/v1/fast-food/grouped"), ("POST", "/api/v1/classify"),
    ("GET", "/api/v1/barcode/8901719117972"), ("POST", "/api/v1/ocr/upload"), ("POST", "/api/v1/ai/coach"),
    ("GET", "/api/v1/homely-meals/user/1"), ("PUT", "/api/v1/settings"), ("POST", "/api/v1/user/profile"),
    # legacy spellings used by the existing app
    ("GET", "/api/meal-logs/today/1"), ("POST", "/api/meal-logs"), ("GET", "/recipes/top"),
    ("GET", "/users/1/targets"), ("POST", "/calculate-profile"), ("POST", "/generate-meal-plan"),
    ("POST", "/track-weight"), ("POST", "/api/ocr"), ("GET", "/api/barcode/123"), ("GET", "/api/analytics/1"),
])
def test_user_routes_go_to_ms3_with_jwt(method, path):
    cfg = get_route_config(method, path)
    assert cfg is not None, path
    assert cfg.target == MS3_USER_URL and cfg.auth_type == "jwt", path


def test_barcode_and_ocr_moved_from_ms1_to_ms3():
    assert get_route_config("GET", "/api/v1/barcode/123").target == MS3_USER_URL
    assert get_route_config("POST", "/api/v1/ocr/upload").target == MS3_USER_URL


def test_scale_ingest_stays_on_ms1_with_device_auth():
    cfg = get_route_config("POST", "/api/v1/ingest/weight-frame")
    assert cfg.target == MS1_CV_URL and cfg.auth_type == "device-token"


def test_ai_routes_get_long_timeouts():
    assert get_route_config("POST", "/api/v1/ai/coach").timeout >= 90
    assert get_route_config("POST", "/api/ai/coach").timeout >= 90
    assert get_route_config("POST", "/api/v1/recipes/generate-instructions").timeout >= 90


def test_unknown_paths_are_not_routed():
    assert get_route_config("GET", "/api/v1/nope") is None
    assert get_route_config("GET", "/admin") is None
    assert get_route_config("GET", "/openapi.json") is None


def test_live_stream_route_has_a_long_read_timeout():
    cfg = get_route_config("GET", "/api/v1/user/stream")
    assert cfg.target == MS3_USER_URL and cfg.auth_type == "jwt" and cfg.timeout >= 120
