"""Greenhouse public Job Board API connector."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from nerve_center.discovery.fetching import HttpFetcher
from nerve_center.discovery.models import (
    Company,
    ConnectorScanResult,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    ScanStatus,
)
from nerve_center.discovery.normalization import (
    canonicalize_url,
    clean_html_text,
    infer_work_arrangement,
    parse_datetime,
    stable_opening_id,
)


class GreenhouseConnector:
    kind = "greenhouse"
    parser_version = "greenhouse-v1"

    async def scan(
        self,
        company: Company,
        source: DiscoverySource,
        fetcher: HttpFetcher,
    ) -> ConnectorScanResult:
        board_token = str(source.configuration.get("board_token") or "").strip()
        if not board_token:
            raise ValueError("Greenhouse source requires board_token")
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
        response = await fetcher.get(url, params={"content": "true"})
        if response.challenged:
            return ConnectorScanResult(
                status=ScanStatus.CHALLENGED,
                requests_made=1,
                http_status=response.status_code,
            )
        if response.throttled:
            return ConnectorScanResult(
                status=ScanStatus.THROTTLED,
                requests_made=1,
                http_status=response.status_code,
            )
        if response.status_code >= 400:
            return ConnectorScanResult(
                status=ScanStatus.ACCESS_FAILED,
                requests_made=1,
                http_status=response.status_code,
            )
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            return ConnectorScanResult(
                status=ScanStatus.PARSER_FAILED,
                requests_made=1,
                http_status=response.status_code,
            )
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
        openings = [
            item
            for raw in jobs
            if isinstance(raw, dict) and (item := self._normalize(company, source, raw)) is not None
        ]
        return ConnectorScanResult(
            status=ScanStatus.SUCCEEDED,
            openings=openings,
            requests_made=1,
            http_status=response.status_code,
        )

    def _normalize(
        self,
        company: Company,
        source: DiscoverySource,
        raw: dict[str, Any],
    ) -> NormalizedJobOpening | None:
        title = str(raw.get("title") or "").strip()
        absolute_url = str(raw.get("absolute_url") or "").strip()
        external_id = str(raw.get("id") or "").strip() or None
        if not title or not absolute_url:
            return None
        location = raw.get("location")
        location_text = (
            str(location.get("name") or "").strip() if isinstance(location, dict) else ""
        )
        departments = raw.get("departments")
        department = _first_name(departments)
        offices = raw.get("offices")
        locations = [location_text] if location_text else []
        locations.extend(_all_names(offices))
        locations = list(dict.fromkeys(item for item in locations if item))
        description = clean_html_text(str(raw.get("content") or ""))
        canonical_url = canonicalize_url(absolute_url)
        discovered_at = datetime.now(UTC)
        provenance = JobProvenance(
            source_id=source.id,
            connector=self.kind,
            parser_version=self.parser_version,
            source_url=absolute_url,
            external_id=external_id,
            direct_employer_source=True,
            discovered_at=discovered_at,
        )
        return NormalizedJobOpening(
            id=stable_opening_id(company.domain, canonical_url, external_id),
            company_id=company.id,
            company_name=company.canonical_name,
            company_domain=company.domain,
            title=title,
            description=description,
            location_text=location_text or None,
            locations=locations,
            work_arrangement=infer_work_arrangement(location_text, title, description[:1000]),
            employment_type=_metadata_value(raw.get("metadata"), "employment type"),
            department=department,
            source_url=absolute_url,
            canonical_url=canonical_url,
            external_id=external_id,
            updated_at=parse_datetime(raw.get("updated_at")),
            discovered_at=discovered_at,
            provenance=[provenance],
        )


def _all_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item.get("name") or "").strip()
        for item in value
        if isinstance(item, dict) and item.get("name")
    ]


def _first_name(value: object) -> str | None:
    names = _all_names(value)
    return names[0] if names else None


def _metadata_value(value: object, target: str) -> str | None:
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().casefold()
        if name == target:
            item_value = item.get("value")
            return str(item_value).strip() if item_value not in (None, "") else None
    return None
