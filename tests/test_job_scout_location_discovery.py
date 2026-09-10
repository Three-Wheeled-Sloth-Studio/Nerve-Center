import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import select

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    Company,
    ConnectorScanResult,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    ScanStatus,
    SourceKind,
)
from nerve_center.discovery.search import SearchResult, UrlClassification
from nerve_center.discovery.service import ConnectorRegistry, DiscoveryService
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.configuration import JobScoutCoordinator
from nerve_center.plugins.job_scout.discovery_learning import (
    JobScoutDiscoveryRepository,
    StrategyAttemptModel,
    StrategyOutcome,
)
from nerve_center.plugins.job_scout.location_discovery import (
    LocationAwareJobScoutDiscoveryLoop,
    _normalize_legacy_location_strategy_yield,
)
from nerve_center.plugins.job_scout.market import MarketAlias
from nerve_center.plugins.job_scout.settings import JobScoutConfiguration


class _DistantConnector:
    parser_version = "distant-v1"

    async def scan(
        self,
        company: Company,
        source: DiscoverySource,
        _fetcher: Any,
    ) -> ConnectorScanResult:
        opening = NormalizedJobOpening(
            id=f"job-{company.id}",
            company_id=company.id,
            company_name=company.canonical_name,
            company_domain=company.domain,
            title="Product Manager",
            description="Own a public data product.",
            location_text="Minneapolis, MN",
            source_url=f"https://{company.domain}/jobs/1",
            canonical_url=f"https://{company.domain}/jobs/1",
            provenance=[
                JobProvenance(
                    source_id=source.id,
                    connector="fixture",
                    parser_version=self.parser_version,
                    source_url=f"https://{company.domain}/jobs/1",
                    direct_employer_source=True,
                )
            ],
        )
        return ConnectorScanResult(
            status=ScanStatus.SUCCEEDED,
            openings=[opening],
            requests_made=1,
        )


class _Search:
    async def search(self, _query: str) -> list[SearchResult]:
        return [
            SearchResult(
                title="Example Co careers",
                url="https://example.com/careers",
                classification=UrlClassification.COMPANY_CAREER,
                domain="example.com",
            )
        ]


class _Market:
    async def expand(self, locations: list[str], **_kwargs: Any) -> list[MarketAlias]:
        return [
            MarketAlias(item, "configured", 0.0, "configured_starting_location")
            for item in locations
        ]


class _NoExtraSurfaces:
    async def resolve(self, _company: Company) -> list[str]:
        return []


def _build(
    tmp_path: Path,
) -> tuple[
    LocationAwareJobScoutDiscoveryLoop,
    JobScoutDiscoveryRepository,
    JobOpeningRepository,
    Database,
]:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    registry = ConnectorRegistry()
    registry.register(SourceKind.JSON_LD, _DistantConnector())
    discovery = DiscoveryService(companies, sources, jobs, connectors=registry)
    coordinator = JobScoutCoordinator(
        settings,
        database,
        None,
        discovery,
        companies,
        sources,
        jobs,
    )
    coordinator.store.save(
        JobScoutConfiguration(
            target_titles=["Product Manager"],
            locations=["Greensboro, NC"],
            public_job_boards=[],
        )
    )
    learning = JobScoutDiscoveryRepository(database)
    loop = LocationAwareJobScoutDiscoveryLoop(
        settings,
        coordinator,
        discovery,
        companies,
        sources,
        jobs,
        learning,
        market=_Market(),
        search_adapter=_Search(),
        surface_resolver=_NoExtraSurfaces(),
        strategies_per_cycle=1,
    )
    return loop, learning, jobs, database


def test_location_strategy_keeps_distant_job_but_does_not_count_it_as_local_yield(
    tmp_path: Path,
) -> None:
    loop, learning, jobs, database = _build(tmp_path)

    asyncio.run(loop.prepare("run-1"))
    cycle = asyncio.run(loop.cycle("run-1", 1))

    assert cycle.openings_found == 1
    assert cycle.coverage["opportunities_retained"] == 1
    assert jobs.list()[0].location_text == "Minneapolis, MN"
    attempted = [item for item in learning.list_strategies() if item.attempts]
    assert len(attempted) == 1
    assert attempted[0].dimensions["location"] == "Greensboro, NC"
    assert attempted[0].opportunities_retained == 0
    with database.session() as session:
        attempt = session.scalar(select(StrategyAttemptModel))
        assert attempt is not None
        assert attempt.detail["total_opportunities_retained"] == 1
        assert attempt.detail["location_conditioned_retained"] == 0
        assert attempt.detail["yield_scope"] == "location_conditioned"


def test_legacy_location_strategy_opening_credit_is_neutralized_before_relearning(
    tmp_path: Path,
) -> None:
    _loop, learning, _jobs, _database = _build(tmp_path)
    strategy = learning.ensure_strategy(
        {
            "kind": "public_search",
            "anchor": "Product Manager",
            "location": "Greensboro, NC",
        },
        origin="legacy-test",
    )
    learning.record_attempt(
        "old-run",
        1,
        strategy.id,
        "deepen",
        StrategyOutcome(opportunities_retained=12, postings_inspected=12),
    )
    assert learning.get_strategy(strategy.id).opportunities_retained == 12

    changed = _normalize_legacy_location_strategy_yield(learning)

    normalized = learning.get_strategy(strategy.id)
    assert changed == 1
    assert normalized.opportunities_retained == 0
    assert normalized.learned_weight == 1.0
