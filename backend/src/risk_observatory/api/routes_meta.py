"""/healthz and /models."""

from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter

from ..config import SETTINGS
from ..models import ACTIVE_MODELS, MODELS
from ..store import repository as repo
from ..store.connection import connect

router = APIRouter(tags=["meta"])


@router.get("/healthz")
async def healthz() -> dict:
    db_ok = True
    try:
        conn = connect()
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception:
        db_ok = False

    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.5) as c:
            r = await c.get(f"{SETTINGS.ollama_host}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        ollama_ok = False

    return {
        "ok": db_ok and ollama_ok,
        "db": "up" if db_ok else "down",
        "ollama": "reachable" if ollama_ok else "unreachable",
    }


@router.get("/models")
async def models() -> dict:
    """Resolve model names from Ollama and report which are currently loaded."""
    loaded: set[str] = set()
    try:
        async with httpx.AsyncClient(timeout=2.5) as c:
            r = await c.get(f"{SETTINGS.ollama_host}/api/ps")
            if r.status_code == 200:
                for m in r.json().get("models", []):
                    name = m.get("name") or m.get("model")
                    if name:
                        loaded.add(name)
    except Exception:
        pass

    return {
        "active": list(ACTIVE_MODELS),
        "roles": {role: name for role, name in MODELS.items()},
        "loaded": sorted(loaded),
    }


@router.get("/stats")
def stats() -> dict:
    conn = connect()
    try:
        return {"events": repo.count_events(conn)}
    finally:
        conn.close()
