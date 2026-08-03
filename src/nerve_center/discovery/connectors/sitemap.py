"""Public sitemap URL discovery connector."""

from __future__ import annotations

from urllib.parse import urljoin
from xml.etree import ElementTree

from nerve_center.discovery.fetching import HttpFetcher
from nerve_center.discovery.models import (
    Company,
    ConnectorScanResult,
    DiscoverySource,
    ScanStatus,
)
from nerve_center.discovery.normalization import canonicalize_url

_JOB_HINTS = ("job", "jobs", "career", "careers", "position", "opening", "vacancy")


class SitemapConnector:
    kind = "sitemap"
    parser_version = "sitemap-v1"

    async def scan(
        self,
        company: Company,
        source: DiscoverySource,
        fetcher: HttpFetcher,
    ) -> ConnectorScanResult:
        del company
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
        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError:
            return ConnectorScanResult(
                status=ScanStatus.PARSER_FAILED,
                requests_made=1,
                http_status=response.status_code,
            )
        max_urls = min(max(int(source.configuration.get("max_urls") or 5000), 1), 50_000)
        urls: list[str] = []
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1].casefold() != "loc" or not element.text:
                continue
            url = canonicalize_url(urljoin(response.url, element.text.strip()))
            lowered = url.casefold()
            if any(hint in lowered for hint in _JOB_HINTS) and url not in urls:
                urls.append(url)
            if len(urls) >= max_urls:
                break
        return ConnectorScanResult(
            status=ScanStatus.SUCCEEDED,
            discovered_urls=urls,
            requests_made=1,
            http_status=response.status_code,
        )
