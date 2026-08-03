"""Generic schema.org JobPosting JSON-LD connector."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from html.parser import HTMLParser
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
    clean_text,
    infer_work_arrangement,
    parse_datetime,
    stable_opening_id,
)


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._capturing = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attr_map = {key.casefold(): (value or "") for key, value in attrs}
        if attr_map.get("type", "").casefold().split(";")[0].strip() == "application/ld+json":
            self._capturing = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capturing:
            self.blocks.append("".join(self._parts).strip())
            self._capturing = False
            self._parts = []


class JsonLdJobConnector:
    kind = "json_ld"
    parser_version = "json-ld-jobposting-v1"

    async def scan(
        self,
        company: Company,
        source: DiscoverySource,
        fetcher: HttpFetcher,
    ) -> ConnectorScanResult:
        response = await fetcher.get(source.base_url)
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
        parser = _JsonLdParser()
        parser.feed(response.text)
        parser.close()
        openings: list[NormalizedJobOpening] = []
        parse_errors = 0
        for block in parser.blocks:
            if not block:
                continue
            try:
                payload = json.loads(block)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            for raw in _find_job_postings(payload):
                normalized = self._normalize(company, source, response.url, raw)
                if normalized is not None:
                    openings.append(normalized)
        status = ScanStatus.SUCCEEDED
        if parse_errors and not openings:
            status = ScanStatus.PARSER_FAILED
        elif parse_errors:
            status = ScanStatus.PARTIAL
        return ConnectorScanResult(
            status=status,
            openings=openings,
            requests_made=1,
            http_status=response.status_code,
            safe_detail={"invalid_json_ld_blocks": parse_errors},
        )

    def _normalize(
        self,
        company: Company,
        source: DiscoverySource,
        fetched_url: str,
        raw: dict[str, Any],
    ) -> NormalizedJobOpening | None:
        title = clean_text(raw.get("title"))
        canonical_url = canonicalize_url(clean_text(raw.get("url")) or fetched_url)
        if not title or not canonical_url:
            return None
        organization = raw.get("hiringOrganization")
        company_name = company.canonical_name
        if isinstance(organization, dict):
            company_name = clean_text(organization.get("name")) or company_name
        locations = _locations(raw.get("jobLocation"))
        applicant_locations = _applicant_locations(raw.get("applicantLocationRequirements"))
        locations.extend(item for item in applicant_locations if item not in locations)
        location_text = "; ".join(locations) or None
        description = clean_html_text(clean_text(raw.get("description")))
        external_id = _identifier(raw.get("identifier"))
        discovered_at = datetime.now(UTC)
        provenance = JobProvenance(
            source_id=source.id,
            connector=self.kind,
            parser_version=self.parser_version,
            source_url=fetched_url,
            external_id=external_id,
            direct_employer_source=True,
            discovered_at=discovered_at,
        )
        return NormalizedJobOpening(
            id=stable_opening_id(company.domain, canonical_url, external_id),
            company_id=company.id,
            company_name=company_name,
            company_domain=company.domain,
            title=title,
            description=description,
            location_text=location_text,
            locations=locations,
            work_arrangement=infer_work_arrangement(
                raw.get("jobLocationType"),
                location_text,
                title,
                description[:1000],
            ),
            employment_type=_employment_type(raw.get("employmentType")),
            source_url=fetched_url,
            canonical_url=canonical_url,
            external_id=external_id,
            posted_at=parse_datetime(raw.get("datePosted")),
            valid_through=parse_datetime(raw.get("validThrough")),
            discovered_at=discovered_at,
            provenance=[provenance],
        )


def _find_job_postings(value: object) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            result.extend(_find_job_postings(item))
    elif isinstance(value, dict):
        type_value = value.get("@type")
        types = type_value if isinstance(type_value, list) else [type_value]
        if any(str(item).casefold().endswith("jobposting") for item in types if item):
            result.append(value)
        graph = value.get("@graph")
        if graph is not None:
            result.extend(_find_job_postings(graph))
    return result


def _locations(value: object) -> list[str]:
    items = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        address = item.get("address")
        if isinstance(address, str):
            text = clean_text(address)
        elif isinstance(address, dict):
            pieces = [
                clean_text(address.get("addressLocality")),
                clean_text(address.get("addressRegion")),
                clean_text(address.get("addressCountry")),
            ]
            text = ", ".join(item for item in pieces if item)
        else:
            text = clean_text(item.get("name"))
        if text and text not in result:
            result.append(text)
    return result


def _applicant_locations(value: object) -> list[str]:
    items = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in items:
        if isinstance(item, dict):
            text = clean_text(item.get("name"))
            if text and text not in result:
                result.append(text)
    return result


def _identifier(value: object) -> str | None:
    if isinstance(value, dict):
        return clean_text(value.get("value")) or clean_text(value.get("name")) or None
    return clean_text(value) or None


def _employment_type(value: object) -> str | None:
    if isinstance(value, list):
        values = [clean_text(item) for item in value]
        return ", ".join(item for item in values if item) or None
    return clean_text(value) or None
