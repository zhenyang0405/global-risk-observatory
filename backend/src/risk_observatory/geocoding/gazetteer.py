"""Local geocoder backed by GeoNames cities15000.

Called only when E4B emits a location name without lat/lng AND GDELT didn't
pre-geocode. Exact lookup keyed by (name_lower, country_iso2); otherwise
fuzzy fallback via rapidfuzz with cutoff 85.

cities15000.txt columns (TSV, no header):
  0 geonameid          int
  1 name               UTF-8 plain name
  2 asciiname          ASCII variant
  3 alternatenames     comma-separated
  4 latitude           dd.dd
  5 longitude          dd.dd
  6 feature_class
  7 feature_code
  8 country_code       ISO-3166 alpha-2
  ... (more columns ignored)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz, process

from ..config import SETTINGS

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class City:
    name: str
    country: str
    lat: float
    lng: float
    population: int


class Gazetteer:
    """Lazy-load cities15000 into memory once."""

    def __init__(self, path: Path):
        self.path = path
        self._exact: dict[tuple[str, str], City] = {}
        self._by_name: dict[str, list[City]] = {}
        self._all_names: list[str] = []
        self._loaded = False
        self._lock = threading.Lock()

    def _load(self) -> None:
        with self._lock:
            if self._loaded:
                return
            if not self.path.exists():
                log.warning("gazetteer: %s not found; geocoding gap-fill disabled", self.path)
                self._loaded = True
                return
            n = 0
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) < 15:
                        continue
                    name = parts[1]
                    asciiname = parts[2]
                    try:
                        lat = float(parts[4])
                        lng = float(parts[5])
                    except ValueError:
                        continue
                    country = parts[8] or ""
                    try:
                        pop = int(parts[14]) if parts[14] else 0
                    except ValueError:
                        pop = 0
                    city = City(name=name, country=country, lat=lat, lng=lng, population=pop)

                    for variant in {name.lower(), asciiname.lower()}:
                        if not variant:
                            continue
                        # Prefer most-populous for collisions on (name, country).
                        key = (variant, country)
                        existing = self._exact.get(key)
                        if existing is None or pop > existing.population:
                            self._exact[key] = city
                        self._by_name.setdefault(variant, []).append(city)
                    n += 1
            self._all_names = list(self._by_name.keys())
            log.info("gazetteer: loaded %d cities", n)
            self._loaded = True

    def resolve(
        self,
        name: str,
        country_iso: Optional[str] = None,
    ) -> Optional[tuple[float, float]]:
        """Return (lat, lng) for a city name; None if no confident match."""
        hit = self.resolve_full(name, country_iso)
        return (hit.lat, hit.lng) if hit is not None else None

    def resolve_full(
        self,
        name: str,
        country_iso: Optional[str] = None,
    ) -> Optional[City]:
        """Same lookup as resolve() but returns the full City (including the
        ISO-3166 alpha-2 country code). Used by the tool-calling layer so the
        LLM can fill country_iso on the way back."""
        self._load()
        if not self._loaded or not name:
            return None
        n = name.strip().lower()
        if not n:
            return None
        cc = (country_iso or "").upper()[:2]

        if cc:
            hit = self._exact.get((n, cc))
            if hit is not None:
                return hit
        # No country filter: take the most populous match for this exact name.
        candidates = self._by_name.get(n)
        if candidates:
            return max(candidates, key=lambda c: c.population)

        # Fuzzy fallback.
        match = process.extractOne(
            n, self._all_names, scorer=fuzz.WRatio, score_cutoff=85
        )
        if match is None:
            return None
        matched_name, _, _ = match
        candidates = self._by_name.get(matched_name) or []
        if cc:
            scoped = [c for c in candidates if c.country == cc]
            if scoped:
                candidates = scoped
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.population)


_GAZETTEER: Optional[Gazetteer] = None
_GAZ_LOCK = threading.Lock()


def get_gazetteer() -> Gazetteer:
    global _GAZETTEER
    with _GAZ_LOCK:
        if _GAZETTEER is None:
            _GAZETTEER = Gazetteer(SETTINGS.geonames_path)
    return _GAZETTEER
