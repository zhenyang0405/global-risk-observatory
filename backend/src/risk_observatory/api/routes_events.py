"""/events and /events/stream."""

from __future__ import annotations

import asyncio
import json
from queue import Empty
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..schemas import BriefEnvelope, EventEnvelope
from ..store import repository as repo
from ..store.connection import connect
from . import events as sse

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(
    limit: int = Query(120, ge=1, le=500),
    hours: int = Query(6, ge=1, le=168),
    categories: Optional[str] = Query(None, description="comma-separated categories"),
) -> list[dict]:
    cats = [c.strip() for c in categories.split(",")] if categories else None
    conn = connect()
    try:
        rows = repo.recent_events(conn, limit=limit, hours=hours, categories=cats)
    finally:
        conn.close()
    return [e.model_dump(mode="json") for e in rows]


def _sse_format(payload: str) -> bytes:
    return f"data: {payload}\n\n".encode("utf-8")


@router.get("/events/stream")
async def events_stream() -> StreamingResponse:
    q = sse.subscribe()

    async def gen():
        # Initial snapshot of recent events so a fresh client doesn't see an empty map.
        conn = connect()
        try:
            recent = repo.recent_events(conn, limit=120, hours=24)
        finally:
            conn.close()
        for e in reversed(recent):
            yield _sse_format(EventEnvelope(event=e).model_dump_json())

        # Stream new envelopes. Drain queue with a short timeout so we can send
        # keepalives every 15 s and notice client disconnects.
        try:
            while True:
                try:
                    env = await asyncio.to_thread(q.get, True, 15.0)
                except Empty:
                    yield b": keepalive\n\n"
                    continue
                if isinstance(env, EventEnvelope):
                    yield _sse_format(env.model_dump_json())
                # Briefs go on a separate channel; ignore here.
        finally:
            sse.unsubscribe(q)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
