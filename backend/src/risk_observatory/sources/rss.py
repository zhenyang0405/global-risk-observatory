"""RSS pull for a curated handful of world-news feeds.

Uses feedparser (sync). We run it via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import feedparser

from ..schemas import RawArticle, SourceKind


@dataclass(frozen=True)
class Feed:
    source: SourceKind
    url: str
    label: str


CURATED_FEEDS: tuple[Feed, ...] = (
    Feed("reuters", "https://feeds.reuters.com/reuters/worldNews", "Reuters World"),
    Feed("ap", "https://feeds.apnews.com/rss/apf-topnews", "AP Top News"),
    Feed("bbc", "http://feeds.bbci.co.uk/news/world/rss.xml", "BBC World"),
    Feed("aljazeera", "https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera"),
)


def _coerce_dt(struct_time) -> datetime:
    if struct_time is None:
        return datetime.now(timezone.utc)
    try:
        return datetime(*struct_time[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _entry_body(entry) -> str | None:
    # Prefer the full content; fall back to summary.
    if getattr(entry, "content", None):
        for c in entry.content:
            if c.get("type", "").startswith("text") and c.get("value"):
                return c["value"]
    return entry.get("summary") or None


def _fetch_one(feed: Feed) -> list[RawArticle]:
    parsed = feedparser.parse(feed.url)
    out: list[RawArticle] = []
    for e in parsed.entries:
        url = e.get("link")
        title = (e.get("title") or "").strip()
        if not url or not title:
            continue
        published = _coerce_dt(e.get("published_parsed") or e.get("updated_parsed"))
        body = _entry_body(e)
        out.append(
            RawArticle(
                url=url,
                source=feed.source,
                title=title,
                body=body,
                published_at=published,
            )
        )
    return out


async def fetch_all(feeds: Iterable[Feed] = CURATED_FEEDS) -> list[RawArticle]:
    """Pull each feed in a worker thread, flatten, dedupe by URL."""
    feeds = list(feeds)
    results = await asyncio.gather(*(asyncio.to_thread(_fetch_one, f) for f in feeds))
    seen: set[str] = set()
    flat: list[RawArticle] = []
    for batch in results:
        for a in batch:
            if a.url in seen:
                continue
            seen.add(a.url)
            flat.append(a)
    return flat


async def _main_once(feed_name: str | None = None) -> None:
    feeds = CURATED_FEEDS
    if feed_name:
        feeds = tuple(f for f in CURATED_FEEDS if f.source == feed_name)
        if not feeds:
            print(f"unknown feed: {feed_name}")
            return
    articles = await fetch_all(feeds)
    print(f"RSS returned {len(articles)} articles across {len(feeds)} feeds")
    for a in articles[:8]:
        print(f"  - [{a.source}] {a.title[:80]}")


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(_main_once(name))
