"""Deterministic location classification and approximate travel-time scoring."""

from __future__ import annotations

import re
from math import asin, cos, radians, sin, sqrt

from nerve_center.discovery.models import WorkArrangement
from nerve_center.scoring.models import (
    CompanyEnrichment,
    GeoPoint,
    JobEnrichment,
    LocationAssessment,
    LocationPreferences,
    LocationScope,
)


def assess_location(
    *,
    work_arrangement: WorkArrangement,
    job_location: JobEnrichment,
    company: CompanyEnrichment,
    preferences: LocationPreferences,
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
        if not office.relevant_to_function:
            continue
        textual_scope = _textual_office_scope(office.label, office.region, preferences)
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
    region = (job_location.region or "").casefold()
    home_region = (preferences.home_region or "").casefold()
    regional_regions = {item.casefold() for item in preferences.regional_regions}

    rationale: list[str] = []
    confidence_inputs = [job_location.location_confidence]
    if (
        work_arrangement is WorkArrangement.REMOTE
        and effective_minutes is None
        and nearest_office_scope is not None
    ):
        scope = nearest_office_scope
        rationale.append(
            "A verified company location matches a configured local or regional market."
        )
        confidence_inputs.append(nearest_office_confidence or 0.5)
    elif effective_minutes is not None:
        if effective_minutes <= preferences.local_max_commute_minutes:
            scope = LocationScope.LOCAL
            rationale.append(
                f"Estimated travel time is {effective_minutes:.0f} minutes, within the local limit."
            )
            confidence_inputs.append(0.9)
        elif region and (region == home_region or region in regional_regions):
            scope = LocationScope.REGIONAL
            rationale.append(
                "The opportunity is outside local commute range but inside the region."
            )
            confidence_inputs.append(0.8)
        else:
            scope = LocationScope.DISTANT
            rationale.append("The opportunity is outside local and configured regional reach.")
            confidence_inputs.append(0.75)
    elif region and (region == home_region or region in regional_regions):
        scope = LocationScope.REGIONAL
        rationale.append("The opportunity is in a configured regional market.")
        confidence_inputs.append(0.65)
    elif region:
        scope = LocationScope.DISTANT
        rationale.append("The opportunity region is outside configured regional markets.")
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


def _textual_office_scope(
    label: str,
    region: str | None,
    preferences: LocationPreferences,
) -> LocationScope | None:
    office_city, office_region = _location_parts(label, region)
    markets = [*preferences.local_markets]
    if preferences.home_label:
        markets.append(preferences.home_label)
    for market in markets:
        market_city, _market_region = _location_parts(market, None)
        if office_city and market_city and office_city == market_city:
            return LocationScope.LOCAL
    configured_regions = {
        item
        for item in [preferences.home_region, *preferences.regional_regions]
        if item
    }
    if office_region and office_region in {item.casefold() for item in configured_regions}:
        return LocationScope.REGIONAL
    return None


def _location_parts(value: str, explicit_region: str | None) -> tuple[str, str]:
    parts = [" ".join(re.findall(r"[a-z0-9]+", item.casefold())) for item in value.split(",")]
    city = parts[0].removeprefix("remote ").strip() if parts else ""
    region = " ".join(re.findall(r"[a-z0-9]+", (explicit_region or "").casefold()))
    if not region and len(parts) > 1:
        region = parts[-1]
    return city, region
