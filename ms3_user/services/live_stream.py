"""
Server-Sent Events for the live dashboard (`GET /api/v1/user/stream`).

The stream first sends the current daily summary, then one `summary` event whenever the user's macros change
(Redis pub/sub channel `macro_updates:{id}`, published by shared.macro_sync), plus a comment heartbeat so proxies and
the gateway's read timeout never see an idle connection. Without Redis it falls back to polling the cache.

Frames follow the SSE wire format:  `event: summary\\ndata: {...json...}\\n\\n`  (heartbeats are `: ping\\n\\n`).
"""
import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional

from shared.redis_client import get_daily_macros, get_redis_client

logger = logging.getLogger("ms3.live_stream")

HEARTBEAT_SECONDS = 15.0
POLL_SECONDS = 2.0


def sse_frame(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


HEARTBEAT_FRAME = ": ping\n\n"


def build_summary(targets: Dict[str, float], payload: Dict[str, Any], day: str, source: str) -> Dict[str, Any]:
    """The daily-summary body, from a canonical macro payload and the user's targets (shared by REST and SSE)."""
    consumed = {k: float(payload.get(k) or 0.0) for k in targets}
    return {
        "date": day,
        "source": source,
        "consumed": consumed,
        "targets": {k: round(v, 1) for k, v in targets.items()},
        "remaining": {k: round(max(targets[k] - consumed[k], 0.0), 1) for k in targets},
        "percent": {k: round(consumed[k] / targets[k] * 100.0, 1) if targets[k] else 0.0 for k in targets},
        "meals_count": int(payload.get("meals_count") or 0),
        "latest_item": payload.get("latest_item"),
        "updated_at": payload.get("updated_at"),
    }


async def summary_stream(
    user_id: int,
    targets: Dict[str, float],
    snapshot: Callable[[], Dict[str, Any]],
    is_disconnected: Callable[[], Awaitable[bool]],
    *,
    heartbeat_s: float = HEARTBEAT_SECONDS,
    poll_s: float = POLL_SECONDS,
    max_frames: Optional[int] = None,
) -> AsyncIterator[str]:
    """Yield SSE frames until the client disconnects (`max_frames` is for tests)."""
    sent = 0

    def count() -> bool:
        nonlocal sent
        sent += 1
        return max_frames is not None and sent >= max_frames

    first = await asyncio.to_thread(snapshot)
    yield sse_frame("summary", build_summary(targets, first, first.get("date", ""), "snapshot"))
    if count():
        return

    last_sent = time.monotonic()
    client = get_redis_client()
    pubsub = None
    if client is not None:
        try:
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(f"macro_updates:{user_id}")
        except Exception as e:  # fall back to polling
            logger.warning("Redis pub/sub unavailable, polling instead: %s", e)
            pubsub = None

    last_payload = first
    try:
        while not await is_disconnected():
            payload = None
            if pubsub is not None:
                message = await asyncio.to_thread(pubsub.get_message, timeout=1.0)
                if message and message.get("type") == "message":
                    try:
                        payload = json.loads(message["data"])
                    except (TypeError, ValueError):
                        payload = None
            else:
                await asyncio.sleep(poll_s)
                current = await asyncio.to_thread(get_daily_macros, user_id, last_payload.get("date", ""))
                if current and current.get("updated_at") != last_payload.get("updated_at"):
                    payload = current

            if payload:
                last_payload = payload
                yield sse_frame("summary", build_summary(targets, payload, payload.get("date", ""), "live"))
                last_sent = time.monotonic()
                if count():
                    return
            elif time.monotonic() - last_sent >= heartbeat_s:
                yield HEARTBEAT_FRAME
                last_sent = time.monotonic()
                if count():
                    return
    finally:
        if pubsub is not None:
            try:
                pubsub.close()
            except Exception:
                pass
