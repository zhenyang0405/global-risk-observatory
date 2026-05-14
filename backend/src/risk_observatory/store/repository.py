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
) -> PersistedEvent:
    event_id = uuid.uuid4().hex
    classified_at = datetime.now(timezone.utc)

    conn.execute(
        """
        INSERT INTO events
          (id, url, title, summary, primary_location, country_iso, lat, lng,
           category, severity, key_entities, sentiment, source, published_at,
           classified_at, model, latency_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    )


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
