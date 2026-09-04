"""Cheap cached U.S. labor-market expansion from public Census Gazetteer data."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile

import httpx

from nerve_center.config import Settings

_GAZETTEER_ROOT = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer"
)
_GAZETTEER_FILES = {
    "places": "2025_Gaz_place_national.zip",
    "counties": "2025_Gaz_counties_national.zip",
    "cbsa": "2025_Gaz_cbsa_national.zip",
}
_PLACE_SUFFIXES = (
    " city",
    " town",
    " village",
    " borough",
    " municipality",
    " cdp",
)


@dataclass(frozen=True, slots=True)
class MarketAlias:
    label: str
    kind: str
    distance_miles: float
    provenance: str


@dataclass(frozen=True, slots=True)
class _GeoRecord:
    name: str
    state: str
    latitude: float
    longitude: float


class GazetteerMarketExpander:
    """Expand configured U.S. locations using a small, cacheable public reference set."""

    def __init__(
        self,
        settings: Settings,
        *,
        cache_dir: Path | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.cache_dir = cache_dir or settings.module_data_dir("job_scout") / "geography"
        self.timeout_seconds = timeout_seconds

    async def expand(
        self,
        locations: list[str],
        *,
        radius_miles: float = 100.0,
        max_aliases_per_location: int = 18,
    ) -> list[MarketAlias]:
        if not locations:
            return []
        await self._ensure_cache()
        places = _load_records(self.cache_dir / "places.txt", "place")
        counties = _load_records(self.cache_dir / "counties.txt", "county")
        metros = _load_records(self.cache_dir / "cbsa.txt", "cbsa")
        aliases: list[MarketAlias] = []
        for configured in locations:
            anchor = _find_anchor(configured, places)
            aliases.append(
                MarketAlias(
                    label=" ".join(configured.split()),
                    kind="configured",
                    distance_miles=0.0,
                    provenance="configured_starting_location",
                )
            )
            if anchor is None:
                continue
            candidates: list[MarketAlias] = []
            for record in places:
                distance = _distance_miles(anchor, record)
                if distance <= radius_miles and distance > 0.1:
                    candidates.append(
                        MarketAlias(
                            label=_place_label(record),
                            kind="nearby_place",
                            distance_miles=distance,
                            provenance="census_2025_gazetteer_place",
                        )
                    )
            for record in counties:
                distance = _distance_miles(anchor, record)
                if distance <= radius_miles:
                    candidates.append(
                        MarketAlias(
                            label=_county_label(record),
                            kind="nearby_county",
                            distance_miles=distance,
                            provenance="census_2025_gazetteer_county",
                        )
                    )
            nearby_metros = sorted(
                (
                    (_distance_miles(anchor, record), record)
                    for record in metros
                    if _distance_miles(anchor, record) <= radius_miles * 1.25
                ),
                key=lambda item: item[0],
            )[:3]
            for distance, record in nearby_metros:
                candidates.append(
                    MarketAlias(
                        label=record.name,
                        kind="metro_alias",
                        distance_miles=distance,
                        provenance="census_2025_gazetteer_nearest_cbsa",
                    )
                )
            aliases.extend(
                sorted(candidates, key=lambda item: (item.distance_miles, item.label))[
                    :max_aliases_per_location
                ]
            )
        return _deduplicate_aliases(aliases)

    async def _ensure_cache(self) -> None:
        missing = [key for key in _GAZETTEER_FILES if not (self.cache_dir / f"{key}.txt").exists()]
        if not missing:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for key in missing:
                archive = _GAZETTEER_FILES[key]
                response = await client.get(
                    f"{_GAZETTEER_ROOT}/{archive}",
                    headers={"User-Agent": "Nerve-Center-Job-Scout/0.3 (+public-geography-cache)"},
                )
                response.raise_for_status()
                with ZipFile(BytesIO(response.content)) as zipped:
                    member = next(
                        (name for name in zipped.namelist() if name.casefold().endswith(".txt")),
                        None,
                    )
                    if member is None:
                        raise ValueError(
                            f"Census Gazetteer archive {archive} contained no text file"
                        )
                    text = zipped.read(member).decode("utf-8-sig", errors="replace")
                temporary = self.cache_dir / f"{key}.tmp"
                temporary.write_text(text, encoding="utf-8")
                temporary.replace(self.cache_dir / f"{key}.txt")


def _load_records(path: Path, kind: str) -> list[_GeoRecord]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.DictReader(StringIO(text), delimiter="|")
    records: list[_GeoRecord] = []
    for row in reader:
        cleaned = {str(key).strip(): str(value or "").strip() for key, value in row.items()}
        name = cleaned.get("NAME", "")
        latitude = cleaned.get("INTPTLAT", "")
        longitude = cleaned.get("INTPTLONG", "")
        if not name or not latitude or not longitude:
            continue
        try:
            lat = float(latitude)
            lon = float(longitude)
        except ValueError:
            continue
        state = cleaned.get("USPS", "") if kind != "cbsa" else ""
        records.append(_GeoRecord(name=name, state=state, latitude=lat, longitude=lon))
    return records


def _find_anchor(value: str, places: list[_GeoRecord]) -> _GeoRecord | None:
    city, state = _parse_location(value)
    if not city:
        return None
    exact = [
        item
        for item in places
        if city.casefold() in _place_name_aliases(item.name)
        and (not state or item.state.casefold() == state.casefold())
    ]
    return exact[0] if exact else None


def _parse_location(value: str) -> tuple[str, str]:
    parts = [" ".join(item.split()).strip() for item in value.split(",")]
    city = parts[0] if parts else ""
    state = parts[1].split()[0] if len(parts) > 1 and parts[1] else ""
    return city, state


def _place_name_aliases(name: str) -> set[str]:
    normalized = " ".join(name.split()).strip()
    aliases = {normalized.casefold()}
    lowered = normalized.casefold()
    for suffix in _PLACE_SUFFIXES:
        if lowered.endswith(suffix):
            aliases.add(normalized[: -len(suffix)].strip().casefold())
    return aliases


def _place_label(record: _GeoRecord) -> str:
    name = record.name
    lowered = name.casefold()
    for suffix in _PLACE_SUFFIXES:
        if lowered.endswith(suffix):
            name = name[: -len(suffix)].strip()
            break
    return f"{name}, {record.state}" if record.state else name


def _county_label(record: _GeoRecord) -> str:
    return f"{record.name}, {record.state}" if record.state else record.name


def _distance_miles(first: _GeoRecord, second: _GeoRecord) -> float:
    radius = 3958.7613
    lat1 = math.radians(first.latitude)
    lat2 = math.radians(second.latitude)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(second.longitude - first.longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.asin(min(1.0, math.sqrt(value)))


def _deduplicate_aliases(values: list[MarketAlias]) -> list[MarketAlias]:
    result: list[MarketAlias] = []
    seen: set[str] = set()
    for value in values:
        key = value.label.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
