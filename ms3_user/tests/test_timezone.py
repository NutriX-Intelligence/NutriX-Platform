"""
The diary day follows APP_TIMEZONE (default Asia/Kolkata), not the server's clock.

Reproduces the reported bug: at 00:50 India time on the 29th the server clock (UTC) still says the 28th, so a meal
logged without an explicit date used to be filed under a different day than the phone shows.
"""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from ms3_user.main import app
from shared import clock

client = TestClient(app)

# 19:20 UTC on the 28th == 00:50 IST on the 29th (the moment of the bug report)
MOMENT_UTC = datetime(2026, 10, 28, 19, 20, tzinfo=timezone.utc)


def _freeze(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: MOMENT_UTC.astimezone(clock.tzinfo()))


# ── the clock ────────────────────────────────────────────────────────────────
def test_default_timezone_is_india(monkeypatch):
    monkeypatch.delenv("APP_TIMEZONE", raising=False)
    assert clock.tzinfo() == ZoneInfo("Asia/Kolkata")


def test_today_depends_on_the_configured_timezone_across_midnight(monkeypatch):
    _freeze(monkeypatch)
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Kolkata")
    assert clock.today() == date(2026, 10, 29)
    monkeypatch.setenv("APP_TIMEZONE", "UTC")
    assert clock.today() == date(2026, 10, 28)
    monkeypatch.setenv("APP_TIMEZONE", "America/Los_Angeles")
    assert clock.today() == date(2026, 10, 28)


def test_unknown_timezone_falls_back_to_utc(monkeypatch):
    monkeypatch.setenv("APP_TIMEZONE", "Not/AZone")
    assert clock.tzinfo() == timezone.utc


# ── the reported scenario, end to end ───────────────────────────────────────
@pytest.fixture()
def account():
    email = f"tz{datetime.now().timestamp()}@example.com".replace(".", "")
    r = client.post("/api/v1/auth/register", json={"email": email.replace("@examplecom", "@example.com"),
                                                  "password": "secret123", "name": "TZ User"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


def test_meal_without_a_date_lands_on_the_users_day_and_shows_on_today(monkeypatch, account):
    uid, headers = account
    _freeze(monkeypatch)
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Kolkata")

    created = client.post("/api/v1/meal-logs", headers=headers,
                          json={"user_id": uid, "food_name": "Oreo", "calories": 483, "source": "barcode"})
    assert created.status_code == 201 and str(created.json()["log_date"]) == "2026-10-29"

    today_list = client.get(f"/api/v1/meal-logs/today/{uid}?log_date=2026-10-29", headers=headers).json()
    assert [m["food_name"] for m in today_list["logs"]] == ["Oreo"]
    default_day = client.get(f"/api/v1/meal-logs/today/{uid}", headers=headers).json()
    assert default_day["date"] == "2026-10-29" and len(default_day["logs"]) == 1

    summary = client.get("/api/v1/user/daily-summary", headers=headers).json()
    assert summary["date"] == "2026-10-29" and summary["consumed"]["calories"] == 483 and summary["meals_count"] == 1


def test_an_explicit_log_date_always_wins(monkeypatch, account):
    uid, headers = account
    _freeze(monkeypatch)
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Kolkata")
    created = client.post("/api/v1/meal-logs", headers=headers,
                          json={"user_id": uid, "food_name": "Late snack", "calories": 100, "log_date": "2026-10-28"})
    assert str(created.json()["log_date"]) == "2026-10-28"
    assert client.get(f"/api/v1/meal-logs/today/{uid}?log_date=2026-10-28", headers=headers).json()["logs"][0]["food_name"] == "Late snack"
    assert client.get(f"/api/v1/meal-logs/today/{uid}?log_date=2026-10-29", headers=headers).json()["logs"] == []


def test_the_same_moment_in_utc_files_under_the_28th(monkeypatch, account):
    uid, headers = account
    _freeze(monkeypatch)
    monkeypatch.setenv("APP_TIMEZONE", "UTC")
    created = client.post("/api/v1/meal-logs", headers=headers, json={"user_id": uid, "food_name": "X", "calories": 1})
    assert str(created.json()["log_date"]) == "2026-10-28"
