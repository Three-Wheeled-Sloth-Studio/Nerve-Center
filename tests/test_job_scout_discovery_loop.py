import asyncio
from pathlib import Path
from typing import Any

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    ConnectorScanResult,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    ScanStatus,
    SourceKind,
)
from nerve_center.discovery.search import SearchChallengeError, SearchResult, UrlClassification
from nerve_center.discovery.service import ConnectorRegistry, DiscoveryService
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.configuration import JobScoutCoordinator
from nerve_center.plugins.job_scout.discovery_learning import JobScoutDiscoveryRepository
from nerve_center.plugins.job_scout.discovery_loop import JobScoutDiscoveryLoop
from nerve_center.plugins.job_scout.market import MarketAlias
from nerve_center.plugins.job_scout.settings import JobScoutConfiguration


class _FixtureConnector:
    parser_version = "fixture-v1"

    def __init__(self, *, opening: bool = True) -> None:
        self.opening = opening
        self.calls: list[str] = []

    async def scan(
        self, company: Company, source: DiscoverySource, _fetcher: Any
    ) -> ConnectorScanResult:
        self.calls.append(source.id)
        openings: list[NormalizedJobOpening] = []
        if self.opening and source.kind in {SourceKind.JSON_LD, SourceKind.ASHBY}:
            openings.append(
                NormalizedJobOpening(
                    id=f"job-{company.id}",
                    company_id=company.id,
                    company_name=company.canonical_name,
                    company_domain=company.domain,
                    title="Product Manager",
                    description="Own a public data product.",
                    location_text="Greensboro, NC",
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
            )
        return ConnectorScanResult(
            status=ScanStatus.SUCCEEDED,
            openings=openings,
            requests_made=1,
        )


class _FixtureSearch:
    def __init__(
        self, results: list[SearchResult] | None = None, *, challenge: bool = False
    ) -> None:
        self.results = results or []
        self.challenge = challenge
        self.queries: list[str] = []

    async def search(self, query: str) -> list[SearchResult]:
        self.queries.append(query)
        if self.challenge:
            raise SearchChallengeError("synthetic search challenge")
        return self.results


class _FixtureMarket:
    async def expand(self, locations: list[str], **_kwargs: Any) -> list[MarketAlias]:
        result = [
            MarketAlias(item, "configured", 0.0, "configured_starting_location")
            for item in locations
        ]
        if locations:
            result.append(
                MarketAlias(
                    "Winston-Salem, NC",
                    "nearby_place",
                    28.0,
                    "census_2025_gazetteer_place",
                )
            )
        return result


class _FixtureSurfaceResolver:
    async def resolve(self, company: Company) -> list[str]:
        return [f"https://{company.domain}/sitemap.xml"]


def _build_loop(
    tmp_path: Path,
    *,
    search: _FixtureSearch,
    opening: bool = True,
    strategies_per_cycle: int = 2,
) -> tuple[
    JobScoutDiscoveryLoop,
    JobScoutDiscoveryRepository,
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
    JobScoutCoordinator,
]:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    connector = _FixtureConnector(opening=opening)
    registry = ConnectorRegistry()
    registry.register(SourceKind.JSON_LD, connector)
    registry.register(SourceKind.SITEMAP, connector)
    registry.register(SourceKind.ASHBY, connector)
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
    loop = JobScoutDiscoveryLoop(
        settings,
        coordinator,
        discovery,
        companies,
        sources,
        jobs,
        learning,
        market=_FixtureMarket(),
        search_adapter=search,
        surface_resolver=_FixtureSurfaceResolver(),
        strategies_per_cycle=strategies_per_cycle,
    )
    return loop, learning, companies, sources, jobs, coordinator


def test_company_first_cycle_persists_company_source_sitemap_and_opening(
    tmp_path: Path,
) -> None:
    search = _FixtureSearch(
        [
            SearchResult(
                title="Example Co careers",
                url="https://example.com/careers",
                classification=UrlClassification.COMPANY_CAREER,
                domain="example.com",
            )
        ]
    )
    loop, learning, companies, sources, jobs, _coordinator = _build_loop(
        tmp_path,
        search=search,
        strategies_per_cycle=2,
    )

    prepared = asyncio.run(loop.prepare("run-1"))
    cycle = asyncio.run(loop.cycle("run-1", 1))

    assert prepared["location_aliases"] == 2
    assert cycle.strategies_attempted == 2
    assert cycle.useful_yield == 4
    assert cycle.openings_found == 1
    assert len(companies.list()) == 1
    company = companies.list()[0]
    assert company.domain == "example.com"
    assert learning.company_evidence_count(company.id) >= 1
    assert {item.kind for item in sources.list()} == {SourceKind.JSON_LD, SourceKind.SITEMAP}
    assert len(jobs.list()) == 1
    assert cycle.coverage["companies_discovered"] == 1
    assert cycle.coverage["career_sources_resolved"] >= 2
    assert cycle.coverage["postings_inspected"] >= 1
    assert cycle.coverage["market_relevant_opportunities"] == 1


def test_zero_opening_company_remains_durable_market_evidence(tmp_path: Path) -> None:
    search = _FixtureSearch(
        [
            SearchResult(
                title="Quiet Co careers",
                url="https://quiet.example/careers",
                classification=UrlClassification.COMPANY_CAREER,
                domain="quiet.example",
            )
        ]
    )
    loop, learning, companies, _sources, jobs, _coordinator = _build_loop(
        tmp_path,
        search=search,
        opening=False,
        strategies_per_cycle=1,
    )

    asyncio.run(loop.prepare("run-1"))
    cycle = asyncio.run(loop.cycle("run-1", 1))

    assert cycle.openings_found == 0
    assert len(jobs.list()) == 0
    assert len(companies.list()) == 1
    assert learning.company_evidence_count(companies.list()[0].id) >= 1
    assert cycle.coverage["companies_discovered"] == 1


def test_public_search_strategy_bounds_result_deepening(tmp_path: Path) -> None:
    search = _FixtureSearch(
        [
            SearchResult(
                title=f"Company {index} careers",
                url=f"https://company-{index}.example/careers",
                classification=UrlClassification.COMPANY_CAREER,
                domain=f"company-{index}.example",
            )
            for index in range(10)
        ]
    )
    loop, _learning, companies, _sources, _jobs, _coordinator = _build_loop(
        tmp_path,
        search=search,
        opening=False,
        strategies_per_cycle=1,
    )

    asyncio.run(loop.prepare("run-1"))
    cycle = asyncio.run(loop.cycle("run-1", 1))

    assert cycle.coverage["results_examined"] == 6
    assert len(companies.list()) == 6


def test_search_seed_cap_preserves_anchor_diversity(tmp_path: Path) -> None:
    loop, learning, _companies, _sources, _jobs, _coordinator = _build_loop(
        tmp_path,
        search=_FixtureSearch(),
    )

    loop._seed_search_strategies(
        [f"Role family {index}" for index in range(20)],
        [f"Market {index}" for index in range(12)],
        ["board-one.example", "board-two.example"],
    )

    anchors = {
        item.dimensions.get("anchor")
        for item in learning.list_strategies()
        if item.dimensions.get("kind") == "public_search"
    }
    locations = {
        item.dimensions.get("location")
        for item in learning.list_strategies()
        if item.dimensions.get("kind") == "public_search"
    }
    source_domains = {
        item.dimensions.get("source_domain")
        for item in learning.list_strategies()
        if item.dimensions.get("kind") == "public_search"
    }
    assert len(anchors) == 20
    assert len(locations) == 12
    assert source_domains == {"web", "board-one.example", "board-two.example"}


def test_company_deepening_attributes_ashby_source_to_known_employer(tmp_path: Path) -> None:
    loop, learning, companies, sources, jobs, _coordinator = _build_loop(
        tmp_path,
        search=_FixtureSearch(),
    )
    company = companies.upsert(
        Company(
            id="company-1",
            canonical_name="Known Employer",
            domain="known.example",
            career_url="https://known.example/careers",
        )
    )
    strategy = learning.ensure_strategy(
        {"kind": "company_revisit", "company_id": company.id},
        origin="test",
    )

    class AshbySurface:
        async def resolve(self, _company: Company) -> list[str]:
            return ["https://jobs.ashbyhq.com/known-employer"]

    loop.surface_resolver = AshbySurface()
    source_ids, _requests, postings = asyncio.run(
        loop._deepen_company(company, strategy.id)
    )

    ashby_sources = [item for item in sources.list() if item.kind is SourceKind.ASHBY]
    assert source_ids == {ashby_sources[0].id}
    assert ashby_sources[0].company_id == company.id
    assert postings == 1
    assert jobs.list()[0].company_id == company.id


def test_major_board_results_are_retained_as_secondary_provenance(
    tmp_path: Path,
) -> None:
    search = _FixtureSearch(
        [
            SearchResult(
                title="Product Director via Built In",
                url="https://builtin.com/job/product-director/42",
                classification=UrlClassification.MAJOR_JOB_BOARD,
                domain="builtin.com",
            )
        ]
    )
    loop, _learning, _companies, sources, jobs, _coordinator = _build_loop(
        tmp_path,
        search=search,
        strategies_per_cycle=1,
    )

    asyncio.run(loop.prepare("run-1"))
    cycle = asyncio.run(loop.cycle("run-1", 1))

    assert cycle.openings_found == 1
    assert len(jobs.list()) == 1
    assert sources.list()[0].configuration["direct_employer_source"] is False


def test_search_challenge_does_not_block_known_source_path(tmp_path: Path) -> None:
    search = _FixtureSearch(challenge=True)
    loop, _learning, companies, sources, _jobs, coordinator = _build_loop(
        tmp_path,
        search=search,
        strategies_per_cycle=2,
    )
    companies.upsert(
        Company(
            id="known-company",
            canonical_name="Known Co",
            domain="known.example",
            career_url="https://known.example/careers",
        )
    )
    sources.upsert(
        DiscoverySource(
            id="known-source",
            company_id="known-company",
            name="Known careers",
            kind=SourceKind.JSON_LD,
            acquisition_class=AcquisitionClass.PUBLIC_HTML_ALLOWED,
            base_url="https://known.example/careers",
            parser_version="fixture-v1",
            scan_interval_minutes=coordinator.store.load().scan_interval_minutes,
        )
    )

    asyncio.run(loop.prepare("run-1"))
    cycle = asyncio.run(loop.cycle("run-1", 1))

    assert cycle.strategies_attempted == 2
    assert cycle.openings_found >= 1
    assert cycle.warnings == ["synthetic search challenge"]
    assert cycle.coverage["known_company_sources_revisited"] >= 1


def test_exhaustion_reflects_then_accepts_manager_routed_strategy(tmp_path: Path) -> None:
    search = _FixtureSearch([])
    loop, learning, _companies, _sources, _jobs, _coordinator = _build_loop(
        tmp_path,
        search=search,
        strategies_per_cycle=20,
    )

    asyncio.run(loop.prepare("run-1"))
    first = asyncio.run(loop.cycle("run-1", 1))
    exhausted = asyncio.run(loop.cycle("run-1", 2))
    reflected = loop.deterministic_reflection("run-1", 2)

    assert first.useful_yield == 0
    assert exhausted.strategies_exhausted is True
    assert exhausted.needs_reflection is True
    assert reflected == {"new_strategies": 0, "llm_recommended": True}
    work = loop.reflection_work_request("run-1", 2)
    assert work["work_class"] == "llm"
    assert work["task_id"] == "job_scout.discovery.reflect"
    assert "authenticated LinkedIn" in work["payload"]["system_prompt"]

    learning.record_reflection_request("request-1", "run-1", 2)
    created = loop.apply_reflection_result(
        "request-1",
        {
            "strategies": [
                {
                    "anchor": "data platform product lead",
                    "location": "Greensboro, NC",
                    "source_domain": "web",
                    "employer_archetype": "regional health technology",
                    "rationale": "The deterministic pass did not try this employer archetype.",
                }
            ]
        },
    )

    assert created == 1
    assert learning.reflection_request("request-1")["status"] == "applied"
    assert learning.session("run-1").coverage["reflection_hypotheses"] == 1
