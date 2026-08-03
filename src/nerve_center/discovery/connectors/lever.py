"""Lever public Postings API connector."""

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
    clean_text,
    infer_work_arrangement,
    parse_datetime,
    stable_opening_id,
)


class LeverConnector:
    kind = "lever"
    parser_version = "lever-v1"

    async def scan(
        self,
        company: Company,
        source: DiscoverySource,
        fetcher: HttpFetcher,
    ) -> ConnectorScanResult:
        site = str(source.configuration.get("site") or "").strip()
        if not site:
            raise ValueError("Lever source requires site")
        region = str(source.configuration.get("region") or "global").casefold()
        host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
        base_url = f"https://{host}/v0/postings/{site}"
        limit = min(max(int(source.configuration.get("page_size") or 100), 1), 100)
        max_pages = min(max(int(source.configuration.get("max_pages") or 20), 1), 100)
        openings: list[NormalizedJobOpening] = []
        requests_made = 0
        last_status: int | None = None
        for page in range(max_pages):
            response = await fetcher.get(
                base_url,
                params={"mode": "json", "skip": page * limit, "limit": limit},
                headers={"Accept": "application/json"},
            )
            requests_made += 1
            last_status = response.status_code
            if response.challenged:
                return ConnectorScanResult(
                    status=ScanStatus.CHALLENGED,
                    openings=openings,
                    requests_made=requests_made,
                    http_status=last_status,
                )
            if response.throttled:
                return ConnectorScanResult(
                    status=ScanStatus.THROTTLED,
                    openings=openings,
                    requests_made=requests_made,
                    http_status=last_status,
                )
            if response.status_code >= 400:
                return ConnectorScanResult(
                    status=ScanStatus.ACCESS_FAILED,
                    openings=openings,
                    requests_made=requests_made,
                    http_status=last_status,
                )
            try:
                payload = json.loads(response.text)
            except json.JSONDecodeError:
                return ConnectorScanResult(
                    status=ScanStatus.PARSER_FAILED,
                    openings=openings,
                    requests_made=requests_made,
                    http_status=last_status,
                )
            if not isinstance(payload, list):
                return ConnectorScanResult(
                    status=ScanStatus.PARSER_FAILED,
                    openings=openings,
                    requests_made=requests_made,
                    http_status=last_status,
                )
            for raw in payload:
                if isinstance(raw, dict):
                    normalized = self._normalize(company, source, raw)
                    if normalized is not None:
                        openings.append(normalized)
            if len(payload) < limit:
                break
        status = ScanStatus.SUCCEEDED if requests_made < max_pages else ScanStatus.PARTIAL
        return ConnectorScanResult(
            status=status,
            openings=openings,
            requests_made=requests_made,
            http_status=last_status,
            safe_detail={"pagination_limit_reached": status is ScanStatus.PARTIAL},
        )

    def _normalize(
        self,
        company: Company,
        source: DiscoverySource,
        raw: dict[str, Any],
    ) -> NormalizedJobOpening | None:
        title = str(raw.get("text") or "").strip()
        hosted_url = str(raw.get("hostedUrl") or "").strip()
        external_id = str(raw.get("id") or "").strip() or None
        if not title or not hosted_url:
            return None
        categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
        all_locations = categories.get("allLocations")
        locations = (
            [clean_text(item) for item in all_locations]
            if isinstance(all_locations, list)
            else []
        )
        location_text = clean_text(categories.get("location"))
        if location_text and location_text not in locations:
            locations.insert(0, location_text)
        description_parts = [
            clean_text(raw.get("descriptionPlain")),
            clean_html_text(str(raw.get("description") or "")),
        ]
        lists = raw.get("lists")
        if isinstance(lists, list):
            for item in lists:
                if not isinstance(item, dict):
                    continue
                description_parts.append(clean_text(item.get("text")))
                description_parts.append(clean_html_text(str(item.get("content") or "")))
        description_parts.extend(
            [
                clean_text(raw.get("additionalPlain")),
                clean_html_text(str(raw.get("additional") or "")),
            ]
        )
        description = "\n".join(dict.fromkeys(item for item in description_parts if item))
        canonical_url = canonicalize_url(hosted_url)
        discovered_at = datetime.now(UTC)
        workplace_type = raw.get("workplaceType")
        provenance = JobProvenance(
            source_id=source.id,
            connector=self.kind,
            parser_version=self.parser_version,
            source_url=hosted_url,
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
            locations=list(dict.fromkeys(item for item in locations if item)),
            work_arrangement=infer_work_arrangement(
                workplace_type,
                location_text,
                title,
                description[:1000],
            ),
            employment_type=clean_text(categories.get("commitment")) or None,
            department=clean_text(categories.get("department")) or None,
            team=clean_text(categories.get("team")) or None,
            source_url=hosted_url,
            canonical_url=canonical_url,
            apply_url=str(raw.get("applyUrl") or "").strip() or None,
            external_id=external_id,
            posted_at=parse_datetime(raw.get("createdAt")),
            discovered_at=discovered_at,
            provenance=[provenance],
        )
