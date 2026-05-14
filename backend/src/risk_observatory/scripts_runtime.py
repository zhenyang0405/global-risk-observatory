"""In-package runtime scripts (kept separate from /scripts which is dev-only)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .ingestion.extractor import classify_many
from .schemas import RawArticle

log = logging.getLogger(__name__)

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / ".." / "scenarios" / "gdelt_fixture.json"


async def seed_demo() -> None:
    """Load scenarios/gdelt_fixture.json and classify each entry via E4B."""
    path = _FIXTURE_PATH.resolve()
    if not path.exists():
        print(f"fixture not found: {path}")
        return
    data = json.loads(path.read_text())
    now = datetime.now(timezone.utc)
    articles: list[RawArticle] = []
    for i, item in enumerate(data):
        articles.append(
            RawArticle(
                url=item.get("url") or f"fixture://seed/{i}",
                source=item.get("source", "manual"),
                title=item["title"],
                body=item.get("body"),
                published_at=datetime.fromisoformat(item["published_at"])
                if "published_at" in item
                else now,
                gdelt_country=item.get("country"),
                gdelt_lat=item.get("lat"),
                gdelt_lng=item.get("lng"),
            )
        )
    print(f"seeding {len(articles)} fixture articles via E4B ...")
    n = await classify_many(articles, concurrency=2)
    print(f"seeded {n} events")
