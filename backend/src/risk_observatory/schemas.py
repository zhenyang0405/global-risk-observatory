"""Pydantic schemas. Kept in lockstep with frontend/src/lib/types.ts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---- canonical enums ----

RiskCategory = Literal[
    "conflict",
    "protest",
    "disaster",
    "disease",
    "economic",
    "displacement",
    "other",
]

Severity = Literal["low", "medium", "high", "critical"]

Escalation = Literal["cooling", "steady", "escalating"]

SourceKind = Literal[
    "gdelt",
    "reuters",
    "ap",
    "bbc",
    "aljazeera",
    "manual",
    "usgs",
    "eonet",
]


# ---- raw input ----


class RawArticle(BaseModel):
    """A pre-classification article fetched from GDELT or RSS."""

    url: str
    source: SourceKind
    title: str
    body: Optional[str] = None
    published_at: datetime
    gdelt_country: Optional[str] = None
    gdelt_lat: Optional[float] = None
    gdelt_lng: Optional[float] = None
    # Source-attached image (e.g. GDELT socialimage). Only set when the host
    # passes SETTINGS.image_source_allowlist. When present, the extractor will
    # try a vision pass instead of text-only.
    image_url: Optional[str] = None


# ---- structured (pre-classified, pre-geocoded) input ----


class StructuredEvent(BaseModel):
    """A pre-classified, pre-geocoded risk event.

    Used by sources that ship lat/lng + category in the payload (USGS,
    NASA EONET). Bypasses the E4B extractor and is inserted directly into the
    DB via repository.insert_structured_event(). The shape mirrors the fields
    of IngestedEvent so the downstream PersistedEvent contract stays uniform.
    """

    url: str
    source: SourceKind
    title: str = Field(max_length=120)
    summary: str = Field(max_length=240)
    primary_location: str
    country_iso: Optional[str] = Field(default=None, max_length=3)
    lat: float = Field(ge=-90.0, le=90.0)
    lng: float = Field(ge=-180.0, le=180.0)
    category: RiskCategory
    severity: Severity
    key_entities: list[str] = Field(default_factory=list, max_length=8)
    sentiment: float = Field(default=0.0, ge=-1.0, le=1.0)
    published_at: datetime


# ---- E4B output ----


class IngestedEvent(BaseModel):
    """Schema-enforced output from gemma4:e4b. One per article."""

    title: str = Field(max_length=120)
    summary: str = Field(max_length=240)
    primary_location: str
    country_iso: Optional[str] = Field(default=None, max_length=3)
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    category: RiskCategory
    severity: Severity
    key_entities: list[str] = Field(default_factory=list, max_length=8)
    sentiment: float = Field(ge=-1.0, le=1.0)
    # Populated only on the image-extraction path. One factual sentence
    # describing what is visible in the photo (not the article).
    image_caption: Optional[str] = Field(default=None, max_length=240)


class PersistedEvent(BaseModel):
    """An IngestedEvent plus identity + bookkeeping. What the API returns."""

    id: str
    url: str
    title: str
    summary: str
    primary_location: str
    country_iso: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    category: RiskCategory
    severity: Severity
    key_entities: list[str]
    sentiment: float
    source: SourceKind
    published_at: datetime
    classified_at: datetime
    model: str
    latency_ms: int
    image_url: Optional[str] = None
    image_local_path: Optional[str] = None
    image_caption: Optional[str] = None


# ---- 26B outputs ----


class EventCluster(BaseModel):
    label: str = Field(max_length=40)
    summary: str = Field(max_length=320)
    event_ids: list[str]
    escalation: Escalation


class ClusterSet(BaseModel):
    """Wraps the cluster list so Ollama schema-format gets a top-level object."""

    clusters: list[EventCluster]


class WorldBrief(BaseModel):
    headline: str = Field(max_length=120)
    hotspots: list[str] = Field(default_factory=list, max_length=5)
    escalation_signals: list[str] = Field(default_factory=list, max_length=5)
    regions_to_watch: list[str] = Field(default_factory=list, max_length=5)
    markdown: str = Field(max_length=4000)


class PersistedBrief(BaseModel):
    id: str
    headline: str
    hotspots: list[str]
    escalation_signals: list[str]
    regions_to_watch: list[str]
    markdown: str
    cluster_ids: list[str]
    created_at: datetime
    model: str
    latency_ms: int


# ---- SSE envelopes ----


class EventEnvelope(BaseModel):
    kind: Literal["event"] = "event"
    event: PersistedEvent


class BriefEnvelope(BaseModel):
    kind: Literal["brief"] = "brief"
    brief: PersistedBrief
