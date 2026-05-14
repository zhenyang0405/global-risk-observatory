"""Background ingestion scheduler. Runs as an asyncio.Task in the app lifespan."""

from __future__ import annotations

import asyncio
import logging

import httpx

from ..api import events as sse
from ..config import SETTINGS
from ..schemas import EventEnvelope, StructuredEvent
from ..sources import eonet, gdelt, rss, usgs
from ..store import repository as repo
from ..store.connection import connect
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


def _persist_structured(ev: StructuredEvent):
    """Synchronous DB write for a structured (pre-geocoded) event.

    Returns the PersistedEvent on success, None if the URL was already seen.
    Runs in a worker thread via asyncio.to_thread().
    """
    conn = connect()
    try:
        if repo.article_exists(conn, ev.url):
            return None
        return repo.insert_structured_event(conn, ev=ev)
    finally:
        conn.close()


async def _structured_tick(
    *,
    name: str,
    fetcher,  # awaitable returning list[StructuredEvent]
) -> None:
    """Shared scaffold for any structured-source tick (USGS, EONET, etc.)."""
    try:
        events = await fetcher
    except Exception as e:  # noqa: BLE001
        log.warning("%s fetch failed: %s", name, e)
        return
    if not events:
        return
    inserted = 0
    for ev in events:
        try:
            persisted = await asyncio.to_thread(_persist_structured, ev)
        except Exception as e:  # noqa: BLE001
            log.warning("%s persist failed for %s: %s", name, ev.url, e)
            continue
        if persisted is not None:
            sse.publish(EventEnvelope(event=persisted))
            inserted += 1
    log.info("%s: %d events fetched, %d new", name, len(events), inserted)


async def _usgs_tick(client: httpx.AsyncClient) -> None:
    await _structured_tick(name="usgs", fetcher=usgs.fetch_events(client=client))


async def _eonet_tick(client: httpx.AsyncClient) -> None:
    await _structured_tick(name="eonet", fetcher=eonet.fetch_events(client=client))


async def run_ingestion_loop() -> None:
    """Interleaved cadences. Structured sources hit DB directly; LLM sources
    share the classify_many pool."""
    gdelt_int = SETTINGS.ingest_gdelt_interval_s
    rss_int = SETTINGS.ingest_rss_interval_s
    usgs_int = SETTINGS.ingest_usgs_interval_s
    eonet_int = SETTINGS.ingest_eonet_interval_s
    if all(i <= 0 for i in (gdelt_int, rss_int, usgs_int, eonet_int)):
        log.info("ingestion loop disabled by config")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Stagger initial ticks so they don't run simultaneously on cold start.
        # Cold-start UX: USGS/EONET fire near-immediately to paint the globe.
        if usgs_int > 0:
            asyncio.create_task(_usgs_periodic(client, usgs_int, initial_delay=2))
        if eonet_int > 0:
            asyncio.create_task(_eonet_periodic(client, eonet_int, initial_delay=5))
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


async def _usgs_periodic(client: httpx.AsyncClient, interval_s: int, initial_delay: int = 0) -> None:
    if initial_delay:
        await asyncio.sleep(initial_delay)
    while True:
        await _usgs_tick(client)
        await asyncio.sleep(interval_s)


async def _eonet_periodic(client: httpx.AsyncClient, interval_s: int, initial_delay: int = 0) -> None:
    if initial_delay:
        await asyncio.sleep(initial_delay)
    while True:
        await _eonet_tick(client)
        await asyncio.sleep(interval_s)
