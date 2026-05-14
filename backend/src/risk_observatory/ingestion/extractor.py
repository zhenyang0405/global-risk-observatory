"""Per-article extraction using gemma4:e4b.

Bounded concurrency via asyncio.Semaphore. On success: insert article + event,
publish to SSE bus. On failure: log and skip (do not poison the loop).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Iterable

from ..api import events as sse
from ..config import SETTINGS
from ..geocoding.gazetteer import get_gazetteer
from ..models import model_for
from ..ollama_client import OPTIONS_INGEST, chat_structured, chat_tools
from ..schemas import EventEnvelope, IngestedEvent, RawArticle
from ..store import repository as repo
from ..store.connection import connect
from .tools import DISPATCH, TOOL_DEFS

log = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "ingest.md"


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _user_prompt(article: RawArticle) -> str:
    bits = [f"TITLE: {article.title}"]
    if article.gdelt_country:
        bits.append(f"REPORTED COUNTRY (GDELT): {article.gdelt_country}")
    if article.body:
        bits.append("")
        bits.append("BODY:")
        bits.append(article.body[:6000])  # keep prompt cheap
    else:
        # GDELT articles have no body; ground extraction on title + reported country.
        bits.append("")
        bits.append("(No body available; classify based on the title and reported country.)")
    return "\n".join(bits)


def _fill_geocoding(ingested: IngestedEvent, article: RawArticle) -> IngestedEvent:
    if ingested.lat is not None and ingested.lng is not None:
        return ingested
    # 1) Prefer GDELT's source lat/lng if present.
    if article.gdelt_lat is not None and article.gdelt_lng is not None:
        return ingested.model_copy(
            update={"lat": article.gdelt_lat, "lng": article.gdelt_lng}
        )
    # 2) Local gazetteer fallback.
    gaz = get_gazetteer()
    hit = gaz.resolve(ingested.primary_location, ingested.country_iso)
    if hit is not None:
        return ingested.model_copy(update={"lat": hit[0], "lng": hit[1]})
    return ingested


async def classify_one(article: RawArticle) -> IngestedEvent | None:
    """Call E4B in a worker thread. Return None on failure.

    If SETTINGS.use_tool_calling is true, the model gets the tool-calling
    layer (lookup_location, classify_severity_by_metric, find_similar_recent_events).
    Otherwise we fall back to single-turn schema-locked extraction, which is
    also the demo-safe path if Gemma 4 tool dialect regresses.
    """
    model = model_for("ingest")
    try:
        if SETTINGS.use_tool_calling:
            ingested, latency_ms, trace = await asyncio.to_thread(
                chat_tools,
                model=model,
                system=_system_prompt(),
                user=_user_prompt(article),
                tools=TOOL_DEFS,
                dispatch=DISPATCH,
                schema=IngestedEvent,
                options=OPTIONS_INGEST,
                max_tool_rounds=3,
            )
            if trace:
                names = ",".join(t["name"] for t in trace)
                log.info("tool_trace[%s] %d call(s): %s", article.url[:60], len(trace), names)
        else:
            ingested, latency_ms = await asyncio.to_thread(
                chat_structured,
                model=model,
                system=_system_prompt(),
                user=_user_prompt(article),
                schema=IngestedEvent,
                options=OPTIONS_INGEST,
            )
    except Exception as e:  # noqa: BLE001
        log.warning("classify failed for %s: %s", article.url, e)
        return None

    # Safety net: if the model never called lookup_location, run the legacy
    # geocoding cascade.
    ingested = _fill_geocoding(ingested, article)
    return ingested, latency_ms, model  # type: ignore[return-value]


async def _persist_and_publish(
    article: RawArticle, ingested: IngestedEvent, model: str, latency_ms: int
) -> None:
    def _do() -> EventEnvelope:
        conn = connect()
        try:
            repo.insert_article(conn, article)
            persisted = repo.insert_event(
                conn, article=article, ingested=ingested, model=model, latency_ms=latency_ms
            )
            return EventEnvelope(event=persisted)
        finally:
            conn.close()

    envelope = await asyncio.to_thread(_do)
    sse.publish(envelope)


async def classify_many(
    articles: Iterable[RawArticle],
    *,
    concurrency: int | None = None,
) -> int:
    """Classify all articles. Returns number of successful inserts."""
    sem = asyncio.Semaphore(concurrency or SETTINGS.ingest_concurrency)
    done = 0
    skipped = 0

    async def _worker(a: RawArticle) -> None:
        nonlocal done, skipped
        # Cheap pre-check: don't even call the LLM if we already have this URL.
        if await asyncio.to_thread(_url_seen, a.url):
            skipped += 1
            return
        async with sem:
            result = await classify_one(a)
        if result is None:
            return
        ingested, latency_ms, model = result
        try:
            await _persist_and_publish(a, ingested, model, latency_ms)
            done += 1
        except Exception as e:  # noqa: BLE001
            log.warning("persist failed for %s: %s", a.url, e)

    await asyncio.gather(*(_worker(a) for a in articles))
    log.info("classify_many: %d ingested, %d skipped (dupe)", done, skipped)
    return done


def _url_seen(url: str) -> bool:
    conn = connect()
    try:
        return repo.article_exists(conn, url)
    finally:
        conn.close()


# ---- one-shot CLI helper (used by `make ingest TEXT="..."`) ----


async def ingest_text_once(text: str) -> None:
    from datetime import datetime, timezone

    article = RawArticle(
        url=f"manual://{abs(hash(text))}",
        source="manual",
        title=text.split(".")[0][:120],
        body=text,
        published_at=datetime.now(timezone.utc),
    )
    result = await classify_one(article)
    if result is None:
        print("classification failed")
        return
    ingested, latency_ms, model = result
    print(json.dumps(ingested.model_dump(), indent=2, default=str))
    print(f"\nmodel={model} latency_ms={latency_ms}")
