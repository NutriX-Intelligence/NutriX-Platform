"""Live dashboard SSE: frame format, snapshot-then-updates, heartbeat, and authentication."""
import asyncio
import json

from fastapi.testclient import TestClient

from ms3_user.main import app
from ms3_user.services import live_stream
from shared.redis_client import set_daily_macros

NO_LEGACY_AUTH = True  # this module checks real authentication (the shim would open an endless stream)

TARGETS = {"calories": 2000.0, "protein_g": 100.0, "carbs_g": 200.0, "fat_g": 50.0}
DAY = "2026-10-27"


def _payload(calories, updated_at, meals=1, item="Apple"):
    return {"user_id": 41, "date": DAY, "calories": calories, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 5.0,
            "meals_count": meals, "latest_item": item, "updated_at": updated_at}


def _parse(frame: str):
    lines = frame.strip().splitlines()
    return lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))


async def _never_disconnected():
    return False


def test_build_summary_math():
    s = live_stream.build_summary(TARGETS, _payload(500.0, "t1"), DAY, "live")
    assert s["consumed"]["calories"] == 500.0 and s["remaining"]["calories"] == 1500.0
    assert s["percent"]["calories"] == 25.0 and s["meals_count"] == 1 and s["latest_item"] == "Apple"
    over = live_stream.build_summary(TARGETS, _payload(2500.0, "t2"), DAY, "live")
    assert over["remaining"]["calories"] == 0.0 and over["percent"]["calories"] == 125.0


def test_sse_frame_format():
    frame = live_stream.sse_frame("summary", {"a": 1})
    assert frame == 'event: summary\ndata: {"a": 1}\n\n'


def test_stream_sends_snapshot_then_each_change():
    async def run():
        frames = []
        set_daily_macros(41, DAY, _payload(100.0, "t1"))
        stream = live_stream.summary_stream(
            41, TARGETS, lambda: _payload(100.0, "t1"), _never_disconnected, poll_s=0.01, heartbeat_s=60, max_frames=3)
        async for frame in stream:
            frames.append(frame)
            if len(frames) == 1:  # a meal is logged after the stream opened
                set_daily_macros(41, DAY, _payload(250.0, "t2", meals=2, item="Roti"))
            elif len(frames) == 2:
                set_daily_macros(41, DAY, _payload(400.0, "t3", meals=3, item="Dal"))
        return frames

    first, second, third = asyncio.run(run())
    kind, body = _parse(first)
    assert kind == "summary" and body["source"] == "snapshot" and body["consumed"]["calories"] == 100.0
    assert _parse(second)[1]["consumed"]["calories"] == 250.0 and _parse(second)[1]["latest_item"] == "Roti"
    assert _parse(third)[1]["source"] == "live" and _parse(third)[1]["consumed"]["calories"] == 400.0


def test_stream_heartbeats_when_nothing_changes():
    async def run():
        set_daily_macros(42, DAY, _payload(100.0, "t1"))
        return [f async for f in live_stream.summary_stream(
            42, TARGETS, lambda: _payload(100.0, "t1"), _never_disconnected, poll_s=0.01, heartbeat_s=0.0, max_frames=2)]

    frames = asyncio.run(run())
    assert frames[1] == live_stream.HEARTBEAT_FRAME


def test_stream_stops_when_the_client_disconnects():
    calls = {"n": 0}

    async def disconnected():
        calls["n"] += 1
        return calls["n"] > 1

    async def run():
        return [f async for f in live_stream.summary_stream(
            43, TARGETS, lambda: _payload(1.0, "t1"), disconnected, poll_s=0.01, heartbeat_s=60)]

    assert len(asyncio.run(run())) == 1  # only the snapshot, then the loop ends


def test_stream_requires_a_token():
    assert TestClient(app).get("/api/v1/user/stream").status_code == 401
