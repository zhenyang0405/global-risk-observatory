"""Per-article extraction using gemma4:e4b.

Bounded concurrency via asyncio.Semaphore. On success: insert article + event,
publish to SSE bus. On failure: log and skip (do not poison the loop).

Each article can take one of two paths:
  - text-only (the default): system=ingest.md, no images.
  - vision (when SETTINGS.ingest_image_enabled and article.image_url is set
    and the image successfully downloads): system=ingest_image.md plus the
    downloaded bytes attached to the user turn.
The vision path falls back to the text path on any failure — image is a bonus.
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
from .image_cache import fetch_and_cache
from .tools import DISPATCH, TOOL_DEFS

log = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_PROMPT_PATH = _PROMPTS_DIR / "ingest.md"
_IMAGE_PROMPT_PATH = _PROMPTS_DIR / "ingest_image.md"


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _image_system_prompt() -> str:
    return _IMAGE_PROMPT_PATH.read_text()


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
    updates: dict = {}
    gaz = get_gazetteer()

    # Resolve the place once so we can pull both coords and country from it.
    city = gaz.resolve_full(ingested.primary_location, ingested.country_iso)

    if ingested.lat is None or ingested.lng is None:
        if article.gdelt_lat is not None and article.gdelt_lng is not None:
            updates["lat"] = article.gdelt_lat
            updates["lng"] = article.gdelt_lng
        elif city is not None:
            updates["lat"] = city.lat
            updates["lng"] = city.lng

    # Safety net: model frequently drops country_iso on the final schema pass
    # even when lookup_location returned one. Fill from the gazetteer or
    # GDELT's reported country whenever it's missing.
    if not ingested.country_iso:
        if city is not None and city.country:
            updates["country_iso"] = city.country
        elif article.gdelt_country:
            updates["country_iso"] = article.gdelt_country[:2].upper()

    return ingested.model_copy(update=updates) if updates else ingested


def _run_chat(
    *,
    model: str,
    system: str,
    user: str,
    images: list[bytes] | None,
) -> tuple[IngestedEvent, int]:
    """Single blocking LLM call shared by the text and vision paths.

    Picks chat_tools vs chat_structured based on SETTINGS.use_tool_calling.
    Tool tracing is logged here so the caller doesn't have to repeat it.
    """
    if SETTINGS.use_tool_calling:
        ingested, latency_ms, trace = chat_tools(
            model=model,
            system=system,
            user=user,
            tools=TOOL_DEFS,
            dispatch=DISPATCH,
            schema=IngestedEvent,
            options=OPTIONS_INGEST,
            max_tool_rounds=3,
            images=images,
        )
        if trace:
            names = ",".join(t["name"] for t in trace)
            log.info("tool_trace %d call(s): %s", len(trace), names)
        return ingested, latency_ms
    return chat_structured(
        model=model,
        system=system,
        user=user,
        schema=IngestedEvent,
        options=OPTIONS_INGEST,
        images=images,
    )


async def classify_one(
    article: RawArticle,
) -> tuple[IngestedEvent, int, str, str | None, str | None] | None:
    """Call E4B in a worker thread. Return None on failure.

    Returns (ingested, latency_ms, model, image_url, image_local_path). The
    last two are set only on the vision path; on the text path they are None.

    Vision-path policy: if SETTINGS.ingest_image_enabled AND article.image_url
    is set AND the image successfully downloads, send the bytes + the image
    system prompt to E4B. If anything in that chain fails, silently fall back
    to the text-only path so the article still gets ingested.
    """
    model = model_for("ingest")
    image_url: str | None = None
    image_local_path: str | None = None
    image_bytes: bytes | None = None
    system_prompt = _system_prompt()

    if SETTINGS.ingest_image_enabled and article.image_url:
        cached = await fetch_and_cache(article.image_url)
        if cached is not None:
            path, image_bytes = cached
            image_url = article.image_url
            # Store just the sha256 stem; the API route owns the extension.
            image_local_path = path.stem
            system_prompt = _image_system_prompt()
        else:
            log.info("image fetch failed; falling back to text-only for %s", article.url)

    try:
        ingested, latency_ms = await asyncio.to_thread(
            _run_chat,
            model=model,
            system=system_prompt,
            user=_user_prompt(article),
            images=[image_bytes] if image_bytes else None,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("classify failed for %s: %s", article.url, e)
        return None

    # Safety net: if the model never called lookup_location, run the legacy
    # geocoding cascade.
    ingested = _fill_geocoding(ingested, article)
    return ingested, latency_ms, model, image_url, image_local_path


async def _persist_and_publish(
    article: RawArticle,
    ingested: IngestedEvent,
    model: str,
    latency_ms: int,
    image_url: str | None,
    image_local_path: str | None,
) -> None:
    def _do() -> EventEnvelope:
        conn = connect()
        try:
            repo.insert_article(conn, article)
            persisted = repo.insert_event(
                conn,
                article=article,
                ingested=ingested,
                model=model,
                latency_ms=latency_ms,
                image_url=image_url,
                image_local_path=image_local_path,
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
        ingested, latency_ms, model, image_url, image_local_path = result
        try:
            await _persist_and_publish(
                a, ingested, model, latency_ms, image_url, image_local_path
            )
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


# ---- one-shot CLI helpers (used by `make ingest` and `make ingest-image`) ----


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
    ingested, latency_ms, model, image_url, image_local_path = result
    print(json.dumps(ingested.model_dump(), indent=2, default=str))
    print(f"\nmodel={model} latency_ms={latency_ms}")


async def ingest_image_once(path_or_url: str, *, title: str | None = None) -> None:
    """One-shot image ingestion for the CLI.

    Accepts either a local filesystem path or an http(s) URL. Synthesises a
    minimal RawArticle whose `image_url` triggers the vision branch.
    """
    from datetime import datetime, timezone
    from urllib.parse import urlparse

    parsed = urlparse(path_or_url)
    if parsed.scheme in ("http", "https"):
        canonical_url = path_or_url
    else:
        # Local path — normalise to a file:// URL so fetch_and_cache routes correctly.
        canonical_url = "file://" + str(Path(path_or_url).expanduser().resolve())

    synthetic_url = f"manual-image://{abs(hash(canonical_url))}"
    article = RawArticle(
        url=synthetic_url,
        source="manual",
        title=title or "Manual image ingestion",
        body=None,
        published_at=datetime.now(timezone.utc),
        image_url=canonical_url,
    )

    if not SETTINGS.ingest_image_enabled:
        print("INGEST_IMAGE_ENABLED is false; nothing to do")
        return

    result = await classify_one(article)
    if result is None:
        print("classification failed")
        return
    ingested, latency_ms, model, image_url, image_local_path = result
    payload = ingested.model_dump()
    payload["image_url"] = image_url
    payload["image_local_path"] = image_local_path
    print(json.dumps(payload, indent=2, default=str))
    print(f"\nmodel={model} latency_ms={latency_ms}")
