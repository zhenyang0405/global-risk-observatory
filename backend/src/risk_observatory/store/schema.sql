-- Global Risk Observatory storage schema.
-- SQLite + built-in R-tree virtual table. No spatialite dependency.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS articles (
    url           TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT,
    published_at  TEXT NOT NULL,
    fetched_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    gdelt_country TEXT,
    gdelt_lat     REAL,
    gdelt_lng     REAL
);

CREATE INDEX IF NOT EXISTS articles_published_idx
    ON articles(published_at DESC);

CREATE TABLE IF NOT EXISTS events (
    id               TEXT PRIMARY KEY,
    url              TEXT NOT NULL REFERENCES articles(url),
    title            TEXT NOT NULL,
    summary          TEXT NOT NULL,
    primary_location TEXT NOT NULL,
    country_iso      TEXT,
    lat              REAL,
    lng              REAL,
    category         TEXT NOT NULL,
    severity         TEXT NOT NULL,
    key_entities     TEXT NOT NULL DEFAULT '[]',  -- JSON array
    sentiment        REAL NOT NULL,
    source           TEXT NOT NULL,
    published_at     TEXT NOT NULL,
    classified_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model            TEXT NOT NULL,
    latency_ms       INTEGER NOT NULL,
    image_url        TEXT,
    image_local_path TEXT,
    image_caption    TEXT
);

CREATE INDEX IF NOT EXISTS events_classified_idx
    ON events(classified_at DESC);
CREATE INDEX IF NOT EXISTS events_category_idx ON events(category);
CREATE INDEX IF NOT EXISTS events_severity_idx ON events(severity);

-- Bounding-box spatial index. We store a point as a degenerate box so that
-- bbox filters (a, b, c, d) work with rtree_match semantics.
CREATE VIRTUAL TABLE IF NOT EXISTS events_rtree USING rtree(
    id_int,        -- INTEGER primary key tied to events.rowid
    min_lat, max_lat,
    min_lng, max_lng
);

CREATE TABLE IF NOT EXISTS briefs (
    id                  TEXT PRIMARY KEY,
    headline            TEXT NOT NULL,
    hotspots            TEXT NOT NULL DEFAULT '[]',
    escalation_signals  TEXT NOT NULL DEFAULT '[]',
    regions_to_watch    TEXT NOT NULL DEFAULT '[]',
    markdown            TEXT NOT NULL,
    cluster_ids         TEXT NOT NULL DEFAULT '[]',
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model               TEXT NOT NULL,
    latency_ms          INTEGER NOT NULL,
    think_trace         TEXT
);

CREATE TABLE IF NOT EXISTS clusters (
    id          TEXT PRIMARY KEY,
    label       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    event_ids   TEXT NOT NULL,
    escalation  TEXT NOT NULL,
    brief_id    TEXT REFERENCES briefs(id),
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS clusters_brief_idx ON clusters(brief_id);

CREATE INDEX IF NOT EXISTS briefs_created_idx ON briefs(created_at DESC);
