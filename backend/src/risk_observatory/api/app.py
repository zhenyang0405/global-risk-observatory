"""FastAPI app factory + lifespan management.

Lifespan:
  - Open and pre-init the DB (schema applied lazily on first connect).
  - Warm up the gazetteer (loads cities15000 once).
  - Fire-and-forget warmup of both Ollama models.
  - Spawn ingestion + reasoning loops as asyncio tasks.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import SETTINGS
from ..geocoding.gazetteer import get_gazetteer
from ..ingestion.loop import run_ingestion_loop
from ..models import ACTIVE_MODELS
from ..ollama_client import warmup
from ..reasoning.loop import run_reasoning_loop
from ..store.connection import connect
from .routes_brief import router as brief_router
from .routes_events import router as events_router
from .routes_images import router as images_router
from .routes_meta import router as meta_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("risk-observatory starting")

    # 1. DB
    conn = connect()
    conn.close()
    log.info("db: %s", SETTINGS.db_path)

    # 2. Gazetteer (lazy-ish — fire in worker thread so we don't block startup)
    asyncio.create_task(asyncio.to_thread(get_gazetteer()._load))

    # 3. Warm both models in parallel (fire-and-forget)
    for model in ACTIVE_MODELS:
        asyncio.create_task(asyncio.to_thread(warmup, model))
    log.info("warming models: %s", ACTIVE_MODELS)

    # 4. Background loops
    ingestion_task = asyncio.create_task(run_ingestion_loop())
    reasoning_task = asyncio.create_task(run_reasoning_loop())

    try:
        yield
    finally:
        log.info("risk-observatory shutting down")
        ingestion_task.cancel()
        reasoning_task.cancel()
        for t in (ingestion_task, reasoning_task):
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass


app = FastAPI(title="Global Risk Observatory", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[SETTINGS.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(meta_router)
app.include_router(events_router)
app.include_router(brief_router)
app.include_router(images_router)
