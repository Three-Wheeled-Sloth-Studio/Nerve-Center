"""Deterministic location classification and approximate travel-time scoring."""

from __future__ import annotations

import re
from math import asin, cos, radians, sin, sqrt

from nerve_center.discovery.models import NormalizedJobOpening, WorkArrangement
from nerve_center.scoring.models import (
    CompanyEnrichment,
    GeoPoint,
    JobEnrichment,
    LocationAssessment,
    LocationPreferences,
    LocationScope,
)

_US_STATE_ALIASES = {
    "al": "al", "alabama": "al", "ak": "ak", "alaska": "ak",
    "az": "az", "arizona": "az", "ar": "ar", "arkansas": "ar",
    "ca": "ca", "california": "ca", "co": "co", "colorado": "co",
    "ct": "ct", "connecticut": "ct", "de": "de", "delaware": "de",
    "fl": "fl", "florida": "fl", "ga": "ga", "georgia": "ga",
    "hi": "hi", "hawaii": "hi", "id": "id", "idaho": "id",
    "il": "il", "illinois": "il", "in": "in", "indiana": "in",
    "ia": "ia", "iowa": "ia", "ks": "ks", "kansas": "ks",
    "ky": "ky", "kentucky": "ky", "la": "la", "louisiana": "la",
    "me": "me", "maine": "me", "md": "md", "maryland": "md",
    "ma": "ma", "massachusetts": "ma", "mi": "mi", "michigan": "mi",
    "mn": "mn", "minnesota": "mn", "ms": "ms", "mississippi": "ms",
    "mo": "mo", "missouri": "mo", "mt": "mt", "montana": "mt",
    "ne": "ne", "nebraska": "ne", "nv": "nv", "nevada": "nv",
    "nh": "nh", "new hampshire": "nh", "nj": "nj", "new jersey": "nj",
    "nm": "nm", "new mexico": "nm", "ny": "ny", "new york": "ny",
    "nc": "nc", "north carolina": "nc", "nd": "nd", "north dakota": "nd",
    "oh": "oh", "ohio": "oh", "ok": "ok", "oklahoma": "ok",
    "or": "or", "oregon": "or", "pa": "pa", "pennsylvania": "pa",
    "ri": "ri", "rhode island": "ri", "sc": "sc", "south carolina": "sc",
    "sd": "sd", "south dakota": "sd", "tn": "tn", "tennessee": "tn",
    "tx": "tx", "texas": "tx", "ut": "ut", "utah": "ut",
    "vt": "vt", "vermont": "vt", "va": "va", "virginia": "va",
    "wa": "wa", "washington": "wa", "wv": "wv", "west virginia": "wv",
    "wi": "wi", "wisconsin": "wi", "wy": "wy", "wyoming": "wy",
    "dc": "dc", "district of columbia": "dc",
}
_US_COUNTRY_MARKERS = {"us", "usa", "united states", "united states of america"}
_REMOTE_MARKERS = ("remote", "work from home", "distributed")


def assess_location(
    *,
    work_arrangement: WorkArrangement,
    job_location: JobEnrichment,
    company: CompanyEnrichment,
    preferences: LocationPreferences,
    listing_locations: list[str] | None = None,
    listing_evidence: list[str] | None = None,
) -> LocationAssessment:
    commute_minutes = job_location.commute_minutes
    if commute_minutes is None and preferences.home_point and job_location.point:
        commute_minutes = estimate_drive_minutes(
            preferences.home_point,
            job_location.point,
            preferences,
        )

    nearest_office_id: str | None = None
    nearest_office_minutes: float | None = None
    nearest_office_scope: LocationScope | None = None
    nearest_office_confidence: float | None = None
    for office in company.offices:
        if not office.relevant_to_function or not is_specific_physical_location(office.label):
            continue
        textual_scope = _textual_scope(office.label, office.region, preferences)
        if textual_scope is LocationScope.LOCAL or (
            textual_scope is LocationScope.REGIONAL
            and nearest_office_scope is not LocationScope.LOCAL
        ):
            nearest_office_scope = textual_scope
            nearest_office_id = office.id
            nearest_office_confidence = office.confidence
        if preferences.home_point and office.point is not None:
            minutes = estimate_drive_minutes(
                preferences.home_point,
                office.point,
                preferences,
            )
            if nearest_office_minutes is None or minutes < nearest_office_minutes:
                nearest_office_minutes = minutes
                nearest_office_id = office.id
                nearest_office_confidence = office.confidence

    effective_minutes = (
        nearest_office_minutes if work_arrangement is WorkArrangement.REMOTE else commute_minutes
    )
    region = _normalize_region(job_location.region)
    configured_regions = _configured_regions(preferences)

    raw_listing_locations = _clean_labels(listing_locations or [])
    structured_job_location = bool(
        commute_minutes is not None
        or job_location.point is not None
        or region
        or job_location.country
        or job_location.remote_scope
    )
    listing_scope: LocationScope | None = None
    listing_label: str | None = None
    listing_confidence = 0.0
    if raw_listing_locations and not structured_job_location:
        listing_scope, listing_label, listing_confidence = classify_listing_locations(
            raw_listing_locations,
            preferences,
            work_arrangement=work_arrangement,
        )

    rationale: list[str] = []
    confidence_inputs = [job_location.location_confidence]
    if effective_minutes is not None:
        if effective_minutes <= preferences.local_max_commute_minutes:
            scope = LocationScope.LOCAL
            rationale.append(
                f"Estimated travel time is {effective_minutes:.0f} minutes, within the local limit."
            )
            confidence_inputs.append(0.9)
        elif region and region in configured_regions:
            scope = LocationScope.REGIONAL
            rationale.append(
                "The opportunity is outside local commute range but inside the configured region."
            )
            confidence_inputs.append(0.8)
        else:
            scope = LocationScope.DISTANT
            rationale.append("The opportunity is outside local and configured regional reach.")
            confidence_inputs.append(0.75)
    elif work_arrangement is WorkArrangement.REMOTE and nearest_office_scope is not None:
        scope = nearest_office_scope
        rationale.append(
            "A verified company location matches a configured local or regional market."
        )
        confidence_inputs.append(nearest_office_confidence or 0.5)
    elif listing_scope is not None:
        scope = listing_scope
        if listing_label:
            rationale.append(_listing_rationale(scope, listing_label))
        confidence_inputs.append(listing_confidence)
        evidence = _clean_labels(listing_evidence or [])
        if evidence:
            rationale.append(f"Listing location source: {evidence[0]}")
    elif region and region in configured_regions:
        scope = LocationScope.REGIONAL
        rationale.append("The opportunity is in a configured regional market.")
        confidence_inputs.append(0.65)
    elif region:
        scope = LocationScope.DISTANT
        rationale.append("The opportunity region is outside configured regional markets.")
        confidence_inputs.append(0.6)
    elif work_arrangement is WorkArrangement.REMOTE and _has_remote_listing(raw_listing_locations):
        scope = LocationScope.DISTANT
        rationale.append(
            "The listing is remote but has no verified local or regional presence evidence."
        )
        confidence_inputs.append(0.6)
    else:
        scope = LocationScope.UNKNOWN
        rationale.append("Location evidence is incomplete.")
        confidence_inputs.append(0.3)

    score = _location_base_score(scope, work_arrangement)
    if scope is LocationScope.LOCAL and effective_minutes is not None:
        decay = 20 * min(
            effective_minutes / preferences.local_max_commute_minutes,
            1,
        )
        score = max(0, score - decay)
        rationale.append("Closer local opportunities receive a continuous response advantage.")
    if work_arrangement is WorkArrangement.REMOTE and nearest_office_minutes is not None:
        rationale.append("The nearest relevant company office contributes to remote visibility.")

    return LocationAssessment(
        scope=scope,
        commute_minutes=commute_minutes,
        nearest_office_id=nearest_office_id,
        nearest_office_minutes=nearest_office_minutes,
        location_score=round(score, 2),
        confidence=round(sum(confidence_inputs) / len(confidence_inputs), 4),
        rationale=rationale,
    )


def classify_listing_locations(
    labels: list[str],
    preferences: LocationPreferences,
    *,
    work_arrangement: WorkArrangement = WorkArrangement.UNKNOWN,
) -> tuple[LocationScope | None, str | None, float]:
    configured_cities = _configured_local_cities(preferences)
    configured_regions = _configured_regions(preferences)
    saw_specific = False
    saw_distant_country = False
    saw_remote = work_arrangement is WorkArrangement.REMOTE
    first_specific: str | None = None

    for raw in _clean_labels(labels):
        for candidate in _split_location_candidates(raw):
            city, region, country, remote = _location_parts(candidate, None)
            saw_remote = saw_remote or remote
            if city:
                saw_specific = True
                first_specific = first_specific or candidate
            if city and city in configured_cities:
                return LocationScope.LOCAL, candidate, 0.9
            if region and region in configured_regions:
                return LocationScope.REGIONAL, candidate, 0.82
            if country and country != "us":
                saw_distant_country = True
                first_specific = first_specific or candidate
            if region and region not in configured_regions:
                saw_specific = True
                first_specific = first_specific or candidate

    if saw_specific or saw_distant_country:
        return LocationScope.DISTANT, first_specific or labels[0], 0.72
    if saw_remote:
        return LocationScope.DISTANT, labels[0] if labels else None, 0.6
    return None, None, 0.0


def opening_matches_market(opening: NormalizedJobOpening, market: str) -> bool:
    market_city, market_region, _country, _remote = _location_parts(market, None)
    if not market_city and not market_region:
        return False
    labels = _clean_labels([opening.location_text or "", *opening.locations])
    for raw in labels:
        for candidate in _split_location_candidates(raw):
            city, region, _candidate_country, remote = _location_parts(candidate, None)
            if remote and not city and not region:
                continue
            if market_city and city == market_city:
                if not market_region or not region or region == market_region:
                    return True
            if not market_city and market_region and region == market_region:
                return True
    return False


def is_specific_physical_location(label: str) -> bool:
    if not label.strip() or _has_remote_listing([label]):
        return False
    if len(_split_location_candidates(label)) != 1:
        return False
    city, region, country, _remote = _location_parts(label, None)
    if not city:
        return False
    normalized = _normalize_text(city)
    if normalized in {"anywhere", "global", "multiple locations", "nationwide", "worldwide"}:
        return False
    return bool(region or country or "," in label)


def estimate_drive_minutes(
    origin: GeoPoint,
    destination: GeoPoint,
    preferences: LocationPreferences,
) -> float:
    miles = haversine_miles(origin, destination)
    road_miles = miles * preferences.road_distance_factor
    return road_miles / preferences.assumed_drive_mph * 60


def haversine_miles(origin: GeoPoint, destination: GeoPoint) -> float:
    earth_radius_miles = 3958.8
    lat1 = radians(origin.latitude)
    lat2 = radians(destination.latitude)
    delta_lat = radians(destination.latitude - origin.latitude)
    delta_lon = radians(destination.longitude - origin.longitude)
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * earth_radius_miles * asin(sqrt(value))


def _location_base_score(
    scope: LocationScope,
    arrangement: WorkArrangement,
) -> float:
    matrix = {
        (LocationScope.LOCAL, WorkArrangement.HYBRID): 100,
        (LocationScope.LOCAL, WorkArrangement.ON_SITE): 90,
        (LocationScope.LOCAL, WorkArrangement.REMOTE): 80,
        (LocationScope.REGIONAL, WorkArrangement.HYBRID): 75,
        (LocationScope.REGIONAL, WorkArrangement.REMOTE): 65,
        (LocationScope.REGIONAL, WorkArrangement.ON_SITE): 45,
        (LocationScope.DISTANT, WorkArrangement.REMOTE): 30,
        (LocationScope.DISTANT, WorkArrangement.HYBRID): 5,
        (LocationScope.DISTANT, WorkArrangement.ON_SITE): 0,
    }
    return float(matrix.get((scope, arrangement), 40))


def _textual_scope(
    label: str,
    region: str | None,
    preferences: LocationPreferences,
) -> LocationScope | None:
    office_city, office_region, _country, _remote = _location_parts(label, region)
    if office_city and office_city in _configured_local_cities(preferences):
        return LocationScope.LOCAL
    if office_region and office_region in _configured_regions(preferences):
        return LocationScope.REGIONAL
    return None


def _configured_local_cities(preferences: LocationPreferences) -> set[str]:
    markets = [*preferences.local_markets]
    if preferences.home_label:
        markets.append(preferences.home_label)
    return {
        city
        for market in markets
        for city, _region, _country, _remote in [_location_parts(market, None)]
        if city
    }


def _configured_regions(preferences: LocationPreferences) -> set[str]:
    regions = {
        _normalize_region(item)
        for item in [preferences.home_region, *preferences.regional_regions]
        if item
    }
    for market in [*preferences.local_markets, preferences.home_label or ""]:
        _city, region, _country, _remote = _location_parts(market, None)
        if region:
            regions.add(region)
    return {item for item in regions if item}


def _split_location_candidates(value: str) -> list[str]:
    return [
        item.strip(" ,")
        for item in re.split(r"\s*(?:;|\n|\s+OR\s+)\s*", value, flags=re.IGNORECASE)
        if item.strip(" ,")
    ]


def _location_parts(
    value: str,
    explicit_region: str | None,
) -> tuple[str, str, str | None, bool]:
    normalized_value = _normalize_text(value)
    remote = any(marker in normalized_value for marker in _REMOTE_MARKERS)
    parts = [_normalize_text(item) for item in value.split(",") if _normalize_text(item)]
    explicit = _normalize_region(explicit_region)
    region = explicit
    country: str | None = None

    if not region:
        for part in parts[1:]:
            candidate_region = _normalize_region(part)
            if candidate_region:
                region = candidate_region
                break
    if region:
        country = "us"
    else:
        tokens = set(re.findall(r"[a-z0-9]+", normalized_value))
        if normalized_value in _US_COUNTRY_MARKERS or "usa" in tokens or "us" in tokens or "united states" in normalized_value:
            country = "us"
        elif "canada" in normalized_value:
            country = "canada"
        elif "united kingdom" in normalized_value or normalized_value.endswith(" uk"):
            country = "uk"

    city = parts[0] if parts else normalized_value
    city = re.sub(r"^(?:remote|distributed|work from home)\b[\s-]*", "", city).strip()
    if city in _US_COUNTRY_MARKERS or city in {"canada", "united kingdom", "uk"}:
        city = ""
    if remote and not parts[1:] and country is not None:
        city = ""
    return city, region, country, remote


def _normalize_region(value: str | None) -> str:
    normalized = _normalize_text(value or "")
    return _US_STATE_ALIASES.get(normalized, "")


def _normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _clean_labels(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value).split()).strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _has_remote_listing(labels: list[str]) -> bool:
    return any(any(marker in _normalize_text(label) for marker in _REMOTE_MARKERS) for label in labels)


def _listing_rationale(scope: LocationScope, label: str) -> str:
    if scope is LocationScope.LOCAL:
        return f"Listing location '{label}' matches a configured local market."
    if scope is LocationScope.REGIONAL:
        return f"Listing location '{label}' is inside a configured regional market."
    return f"Listing location '{label}' is outside configured local and regional markets."
