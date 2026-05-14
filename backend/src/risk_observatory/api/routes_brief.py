"""/brief endpoints."""

from __future__ import annotations

import asyncio
from queue import Empty

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..reasoning import loop as reasoning_loop
from ..schemas import BriefEnvelope, EventEnvelope
from ..store import repository as repo
from ..store.connection import connect
from . import events as sse

router = APIRouter(tags=["brief"])


@router.get("/brief/latest")
def latest_brief() -> dict | None:
    conn = connect()
    try:
        b = repo.latest_brief(conn)
    finally:
        conn.close()
    return b.model_dump(mode="json") if b else None


@router.post("/brief/run", status_code=202)
def trigger_brief() -> dict:
    reasoning_loop.RUN_NOW.set()
    return {"status": "queued"}


@router.get("/brief/stream")
async def brief_stream() -> StreamingResponse:
    q = sse.subscribe()

    async def gen():
        # Initial snapshot so a fresh client shows the most recent brief.
        conn = connect()
        try:
            latest = repo.latest_brief(conn)
        finally:
            conn.close()
        if latest is not None:
            yield f"data: {BriefEnvelope(brief=latest).model_dump_json()}\n\n".encode()

        try:
            while True:
                try:
                    env = await asyncio.to_thread(q.get, True, 15.0)
                except Empty:
                    yield b": keepalive\n\n"
                    continue
                if isinstance(env, BriefEnvelope):
                    yield f"data: {env.model_dump_json()}\n\n".encode()
        finally:
            sse.unsubscribe(q)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)
