"""Ashby public Job Postings API connector."""

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


class AshbyConnector:
    kind = "ashby"
    parser_version = "ashby-public-postings-v1"

    async def scan(
        self,
        company: Company,
        source: DiscoverySource,
        fetcher: HttpFetcher,
    ) -> ConnectorScanResult:
        board_name = str(source.configuration.get("board_name") or "").strip()
        if not board_name:
            raise ValueError("Ashby source requires board_name")
        response = await fetcher.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{board_name}",
            params={"includeCompensation": "true"},
        )
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
            opening
            for raw in jobs
            if isinstance(raw, dict)
            and raw.get("isListed", True)
            and (opening := self._normalize(company, source, raw)) is not None
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
        job_url = str(raw.get("jobUrl") or "").strip()
        if not title or not job_url:
            return None
        canonical_url = canonicalize_url(job_url)
        apply_url = str(raw.get("applyUrl") or "").strip() or None
        primary_location = str(raw.get("location") or "").strip()
        secondary = raw.get("secondaryLocations")
        locations = [primary_location] if primary_location else []
        if isinstance(secondary, list):
            locations.extend(
                str(item.get("location") or "").strip()
                for item in secondary
                if isinstance(item, dict) and item.get("location")
            )
        locations = list(dict.fromkeys(item for item in locations if item))
        description = str(raw.get("descriptionPlain") or "").strip()
        if not description:
            description = clean_html_text(str(raw.get("descriptionHtml") or ""))
        workplace_type = str(raw.get("workplaceType") or "").strip()
        discovered_at = datetime.now(UTC)
        provenance = JobProvenance(
            source_id=source.id,
            connector=self.kind,
            parser_version=self.parser_version,
            source_url=job_url,
            direct_employer_source=True,
            discovered_at=discovered_at,
        )
        return NormalizedJobOpening(
            id=stable_opening_id(company.domain, canonical_url, None),
            company_id=company.id,
            company_name=company.canonical_name,
            company_domain=company.domain,
            title=title,
            description=description,
            location_text="; ".join(locations) or None,
            locations=locations,
            work_arrangement=infer_work_arrangement(
                workplace_type,
                primary_location,
                title,
                description[:1000],
            ),
            employment_type=str(raw.get("employmentType") or "").strip() or None,
            department=str(raw.get("department") or "").strip() or None,
            team=str(raw.get("team") or "").strip() or None,
            source_url=job_url,
            canonical_url=canonical_url,
            apply_url=canonicalize_url(apply_url) if apply_url else None,
            posted_at=parse_datetime(raw.get("publishedAt")),
            discovered_at=discovered_at,
            provenance=[provenance],
        )
