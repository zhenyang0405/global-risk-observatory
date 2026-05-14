"""Environment-driven configuration. Read once at startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _path(env: str, default: str) -> Path:
    return Path(os.environ.get(env, default)).expanduser().resolve()


def _int(env: str, default: int) -> int:
    try:
        return int(os.environ.get(env, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    ollama_host: str
    db_path: Path
    geonames_path: Path
    model_ingest: str
    model_reason: str
    ingest_gdelt_interval_s: int
    ingest_rss_interval_s: int
    reason_interval_s: int
    ingest_concurrency: int
    api_port: int
    frontend_origin: str


def load_settings() -> Settings:
    return Settings(
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        db_path=_path("OBSERVATORY_DB", "../data/observatory.db"),
        geonames_path=_path("GEONAMES_PATH", "../data/cities15000.txt"),
        model_ingest=os.environ.get("MODEL_INGEST", "gemma4:e4b"),
        model_reason=os.environ.get("MODEL_REASON", "gemma4:26b-a4b"),
        ingest_gdelt_interval_s=_int("INGEST_GDELT_INTERVAL", 900),
        ingest_rss_interval_s=_int("INGEST_RSS_INTERVAL", 1800),
        reason_interval_s=_int("REASON_INTERVAL", 600),
        ingest_concurrency=_int("INGEST_CONCURRENCY", 4),
        api_port=_int("API_PORT", 8000),
        frontend_origin=os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000"),
    )


SETTINGS = load_settings()
