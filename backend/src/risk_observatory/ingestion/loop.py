"""Background ingestion scheduler. Runs as an asyncio.Task in the app lifespan."""

from __future__ import annotations

import asyncio
import logging

import httpx

from ..config import SETTINGS
from ..sources import gdelt, rss
from .extractor import classify_many

log = logging.getLogger(__name__)


async def _gdelt_tick(client: httpx.AsyncClient) -> None:
    try:
        articles = await gdelt.fetch_articles(client=client, timespan="30min", max_records=60)
    except Exception as e:  # noqa: BLE001
        log.warning("gdelt fetch failed: %s", e)
        return
    if not articles:
        return
    log.info("gdelt: %d articles", len(articles))
    await classify_many(articles)


async def _rss_tick() -> None:
    try:
        articles = await rss.fetch_all()
    except Exception as e:  # noqa: BLE001
        log.warning("rss fetch failed: %s", e)
        return
    if not articles:
        return
    log.info("rss: %d articles", len(articles))
    await classify_many(articles)


async def run_ingestion_loop() -> None:
    """Two interleaved cadences sharing the same classify_many pool."""
    gdelt_int = SETTINGS.ingest_gdelt_interval_s
    rss_int = SETTINGS.ingest_rss_interval_s
    if gdelt_int <= 0 and rss_int <= 0:
        log.info("ingestion loop disabled by config")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Stagger initial ticks so they don't run simultaneously on cold start.
        if gdelt_int > 0:
            asyncio.create_task(_gdelt_periodic(client, gdelt_int))
        if rss_int > 0:
            asyncio.create_task(_rss_periodic(rss_int, initial_delay=15))
        # Park forever; subtasks own their own loops.
        while True:
            await asyncio.sleep(3600)


async def _gdelt_periodic(client: httpx.AsyncClient, interval_s: int) -> None:
    while True:
        await _gdelt_tick(client)
        await asyncio.sleep(interval_s)


async def _rss_periodic(interval_s: int, initial_delay: int = 0) -> None:
    if initial_delay:
        await asyncio.sleep(initial_delay)
    while True:
        await _rss_tick()
        await asyncio.sleep(interval_s)
