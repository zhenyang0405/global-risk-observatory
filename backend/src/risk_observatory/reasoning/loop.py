"""Reasoning scheduler. Periodic + on-demand via an asyncio.Event."""

from __future__ import annotations

import asyncio
import logging

from ..api import events as sse
from ..config import SETTINGS
from ..schemas import BriefEnvelope
from ..store import repository as repo
from ..store.connection import connect
from .briefer import write as write_brief
from .clusterer import cluster as run_cluster

log = logging.getLogger(__name__)


# Triggered by POST /brief/run. The loop also self-triggers every interval.
RUN_NOW: asyncio.Event = asyncio.Event()


async def run_once() -> None:
    conn = connect()
    try:
        tail = repo.recent_events(conn, limit=120, hours=6)
    finally:
        conn.close()

    if len(tail) < 3:
        log.info("reasoning skipped: only %d recent events", len(tail))
        return

    clusters = await run_cluster(tail)
    brief, latency_ms, model = await write_brief(clusters, tail[:30])

    def _persist() -> BriefEnvelope:
        c = connect()
        try:
            persisted = repo.insert_brief(
                c, brief=brief, cluster_ids=[], model=model, latency_ms=latency_ms
            )
            # Insert clusters with FK to brief
            cluster_ids = repo.insert_clusters(
                c,
                clusters=[
                    (cl.label, cl.summary, cl.event_ids, cl.escalation)
                    for cl in clusters.clusters
                ],
                brief_id=persisted.id,
            )
            persisted = persisted.model_copy(update={"cluster_ids": cluster_ids})
            return BriefEnvelope(brief=persisted)
        finally:
            c.close()

    envelope = await asyncio.to_thread(_persist)
    sse.publish(envelope)
    log.info("brief written (%d ms, %d clusters)", latency_ms, len(clusters.clusters))


async def run_reasoning_loop() -> None:
    interval = SETTINGS.reason_interval_s
    if interval <= 0:
        log.info("reasoning loop disabled by config (still serves /brief/run)")

    while True:
        try:
            await run_once()
        except Exception as e:  # noqa: BLE001
            log.exception("reasoning failed: %s", e)

        if interval <= 0:
            await RUN_NOW.wait()
            RUN_NOW.clear()
            continue
        try:
            await asyncio.wait_for(RUN_NOW.wait(), timeout=interval)
            RUN_NOW.clear()
        except asyncio.TimeoutError:
            pass
