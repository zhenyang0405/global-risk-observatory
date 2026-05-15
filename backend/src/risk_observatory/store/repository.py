"""DB access patterns. All SQL lives here."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..schemas import (
    IngestedEvent,
    PersistedBrief,
    PersistedEvent,
    RawArticle,
    StructuredEvent,
    WorldBrief,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


# ---- articles ----


def insert_article(conn: sqlite3.Connection, article: RawArticle) -> bool:
    """Returns True if inserted, False if a row with this URL already exists."""
    try:
        conn.execute(
            """
            INSERT INTO articles
              (url, source, title, body, published_at, gdelt_country, gdelt_lat, gdelt_lng)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.url,
                article.source,
                article.title,
                article.body,
                article.published_at.isoformat(),
                article.gdelt_country,
                article.gdelt_lat,
                article.gdelt_lng,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def article_exists(conn: sqlite3.Connection, url: str) -> bool:
    row = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
    return row is not None


# ---- events ----


def insert_event(
    conn: sqlite3.Connection,
    *,
    article: RawArticle,
    ingested: IngestedEvent,
    model: str,
    latency_ms: int,
    image_url: str | None = None,
    image_local_path: str | None = None,
) -> PersistedEvent:
    event_id = uuid.uuid4().hex
    classified_at = datetime.now(timezone.utc)

    conn.execute(
        """
        INSERT INTO events
          (id, url, title, summary, primary_location, country_iso, lat, lng,
           category, severity, key_entities, sentiment, source, published_at,
           classified_at, model, latency_ms,
           image_url, image_local_path, image_caption)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            article.url,
            ingested.title,
            ingested.summary,
            ingested.primary_location,
            ingested.country_iso,
            ingested.lat,
            ingested.lng,
            ingested.category,
            ingested.severity,
            json.dumps(ingested.key_entities),
            ingested.sentiment,
            article.source,
            article.published_at.isoformat(),
            classified_at.isoformat(),
            model,
            latency_ms,
            image_url,
            image_local_path,
            ingested.image_caption,
        ),
    )

    if ingested.lat is not None and ingested.lng is not None:
        rowid = conn.execute(
            "SELECT rowid FROM events WHERE id = ?", (event_id,)
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO events_rtree (id_int, min_lat, max_lat, min_lng, max_lng)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rowid, ingested.lat, ingested.lat, ingested.lng, ingested.lng),
        )

    return PersistedEvent(
        id=event_id,
        url=article.url,
        title=ingested.title,
        summary=ingested.summary,
        primary_location=ingested.primary_location,
        country_iso=ingested.country_iso,
        lat=ingested.lat,
        lng=ingested.lng,
        category=ingested.category,
        severity=ingested.severity,
        key_entities=ingested.key_entities,
        sentiment=ingested.sentiment,
        source=article.source,
        published_at=article.published_at,
        classified_at=classified_at,
        model=model,
        latency_ms=latency_ms,
        image_url=image_url,
        image_local_path=image_local_path,
        image_caption=ingested.image_caption,
    )


def insert_structured_event(
    conn: sqlite3.Connection,
    *,
    ev: StructuredEvent,
) -> PersistedEvent:
    """Insert a pre-classified, pre-geocoded event from a structured feed.

    Synthesises a parent articles row (body=None) to satisfy the events.url ->
    articles.url FK, then inserts the event with model="structured" and
    latency_ms=0. Mirrors insert_event's shape so the SSE/repo contract is
    uniform across LLM and structured paths.
    """
    # Synthetic parent article. insert_article returns False if it already exists
    # (URL is the PK); we treat that as benign because the caller already
    # checked article_exists() and is racing with another worker.
    try:
        conn.execute(
            """
            INSERT INTO articles
              (url, source, title, body, published_at, gdelt_country, gdelt_lat, gdelt_lng)
            VALUES (?, ?, ?, NULL, ?, NULL, ?, ?)
            """,
            (
                ev.url,
                ev.source,
                ev.title,
                ev.published_at.isoformat(),
                ev.lat,
                ev.lng,
            ),
        )
    except sqlite3.IntegrityError:
        # Parent already exists; fine.
        pass

    event_id = uuid.uuid4().hex
    classified_at = datetime.now(timezone.utc)
    model = "structured"
    latency_ms = 0

    conn.execute(
        """
        INSERT INTO events
          (id, url, title, summary, primary_location, country_iso, lat, lng,
           category, severity, key_entities, sentiment, source, published_at,
           classified_at, model, latency_ms,
           image_url, image_local_path, image_caption)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
        """,
        (
            event_id,
            ev.url,
            ev.title,
            ev.summary,
            ev.primary_location,
            ev.country_iso,
            ev.lat,
            ev.lng,
            ev.category,
            ev.severity,
            json.dumps(ev.key_entities),
            ev.sentiment,
            ev.source,
            ev.published_at.isoformat(),
            classified_at.isoformat(),
            model,
            latency_ms,
        ),
    )

    rowid = conn.execute(
        "SELECT rowid FROM events WHERE id = ?", (event_id,)
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO events_rtree (id_int, min_lat, max_lat, min_lng, max_lng)
        VALUES (?, ?, ?, ?, ?)
        """,
        (rowid, ev.lat, ev.lat, ev.lng, ev.lng),
    )

    return PersistedEvent(
        id=event_id,
        url=ev.url,
        title=ev.title,
        summary=ev.summary,
        primary_location=ev.primary_location,
        country_iso=ev.country_iso,
        lat=ev.lat,
        lng=ev.lng,
        category=ev.category,
        severity=ev.severity,
        key_entities=ev.key_entities,
        sentiment=ev.sentiment,
        source=ev.source,
        published_at=ev.published_at,
        classified_at=classified_at,
        model=model,
        latency_ms=latency_ms,
    )


def _row_get(row: sqlite3.Row, key: str) -> object:
    """Tolerant column access — returns None if the column is absent.

    Necessary because older DB files predating the image columns will still
    parse via this function until they're recreated.
    """
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def _row_to_event(row: sqlite3.Row) -> PersistedEvent:
    return PersistedEvent(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        summary=row["summary"],
        primary_location=row["primary_location"],
        country_iso=row["country_iso"],
        lat=row["lat"],
        lng=row["lng"],
        category=row["category"],
        severity=row["severity"],
        key_entities=json.loads(row["key_entities"]),
        sentiment=row["sentiment"],
        source=row["source"],
        published_at=_parse_dt(row["published_at"]),
        classified_at=_parse_dt(row["classified_at"]),
        model=row["model"],
        latency_ms=row["latency_ms"],
        image_url=_row_get(row, "image_url"),  # type: ignore[arg-type]
        image_local_path=_row_get(row, "image_local_path"),  # type: ignore[arg-type]
        image_caption=_row_get(row, "image_caption"),  # type: ignore[arg-type]
    )


def recent_events(
    conn: sqlite3.Connection,
    *,
    limit: int = 120,
    hours: int = 6,
    categories: Optional[list[str]] = None,
) -> list[PersistedEvent]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    sql = "SELECT * FROM events WHERE classified_at >= ?"
    params: list = [cutoff]
    if categories:
        placeholders = ",".join("?" for _ in categories)
        sql += f" AND category IN ({placeholders})"
        params.extend(categories)
    sql += " ORDER BY classified_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_event(r) for r in rows]


def search_recent(
    conn: sqlite3.Connection,
    *,
    query: str,
    hours: int = 12,
    limit: int = 3,
) -> list[PersistedEvent]:
    """LIKE-search recent events for the find_similar_recent_events tool.

    Matches each whitespace-separated token of `query` against the concatenation
    of (title, primary_location, country_iso) case-insensitively. ANDs the
    tokens so all must match; empty query returns nothing.
    """
    tokens = [t.strip() for t in query.lower().split() if t.strip()]
    if not tokens:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    like_clauses = " AND ".join(
        ["LOWER(title || ' ' || primary_location || ' ' || COALESCE(country_iso,'')) LIKE ?"]
        * len(tokens)
    )
    sql = (
        "SELECT * FROM events "
        "WHERE classified_at >= ? "
        f"AND ({like_clauses}) "
        "ORDER BY classified_at DESC LIMIT ?"
    )
    params: list = [cutoff]
    params.extend(f"%{t}%" for t in tokens)
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_event(r) for r in rows]


def events_for_bbox(
    conn: sqlite3.Connection,
    *,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    limit: int = 500,
) -> list[PersistedEvent]:
    rows = conn.execute(
        """
        SELECT events.* FROM events_rtree
        JOIN events ON events.rowid = events_rtree.id_int
        WHERE events_rtree.min_lat >= ?
          AND events_rtree.max_lat <= ?
          AND events_rtree.min_lng >= ?
          AND events_rtree.max_lng <= ?
        ORDER BY events.classified_at DESC
        LIMIT ?
        """,
        (min_lat, max_lat, min_lng, max_lng, limit),
    ).fetchall()
    return [_row_to_event(r) for r in rows]


# ---- briefs ----


def insert_brief(
    conn: sqlite3.Connection,
    *,
    brief: WorldBrief,
    cluster_ids: list[str],
    model: str,
    latency_ms: int,
    think_trace: str | None = None,
) -> PersistedBrief:
    brief_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc)
    conn.execute(
        """
        INSERT INTO briefs
          (id, headline, hotspots, escalation_signals, regions_to_watch, markdown,
           cluster_ids, created_at, model, latency_ms, think_trace)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            brief_id,
            brief.headline,
            json.dumps(brief.hotspots),
            json.dumps(brief.escalation_signals),
            json.dumps(brief.regions_to_watch),
            brief.markdown,
            json.dumps(cluster_ids),
            created_at.isoformat(),
            model,
            latency_ms,
            think_trace,
        ),
    )
    return PersistedBrief(
        id=brief_id,
        headline=brief.headline,
        hotspots=brief.hotspots,
        escalation_signals=brief.escalation_signals,
        regions_to_watch=brief.regions_to_watch,
        markdown=brief.markdown,
        cluster_ids=cluster_ids,
        created_at=created_at,
        model=model,
        latency_ms=latency_ms,
    )


def latest_brief(conn: sqlite3.Connection) -> Optional[PersistedBrief]:
    row = conn.execute(
        "SELECT * FROM briefs ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return PersistedBrief(
        id=row["id"],
        headline=row["headline"],
        hotspots=json.loads(row["hotspots"]),
        escalation_signals=json.loads(row["escalation_signals"]),
        regions_to_watch=json.loads(row["regions_to_watch"]),
        markdown=row["markdown"],
        cluster_ids=json.loads(row["cluster_ids"]),
        created_at=_parse_dt(row["created_at"]),
        model=row["model"],
        latency_ms=row["latency_ms"],
    )


def insert_clusters(
    conn: sqlite3.Connection,
    *,
    clusters: list[tuple[str, str, list[str], str]],
    brief_id: str,
) -> list[str]:
    """clusters = [(label, summary, event_ids, escalation), ...]. Returns inserted cluster ids."""
    ids: list[str] = []
    for label, summary, event_ids, escalation in clusters:
        cid = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO clusters (id, label, summary, event_ids, escalation, brief_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cid, label, summary, json.dumps(event_ids), escalation, brief_id),
        )
        ids.append(cid)
    return ids


def count_events(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
