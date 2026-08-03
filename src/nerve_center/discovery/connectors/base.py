"""Connector contracts and shared helpers."""

from __future__ import annotations

from typing import Protocol

from nerve_center.discovery.fetching import HttpFetcher
from nerve_center.discovery.models import Company, ConnectorScanResult, DiscoverySource


class JobSourceConnector(Protocol):
    kind: str
    parser_version: str

    async def scan(
        self,
        company: Company,
        source: DiscoverySource,
        fetcher: HttpFetcher,
    ) -> ConnectorScanResult: ...
