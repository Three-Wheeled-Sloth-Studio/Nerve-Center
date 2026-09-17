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
from nerve_center.plugins.job_scout.discovery_learning import (
    EMPLOYER_LANDSCAPE_EVIDENCE_REVISION,
    JobScoutDiscoveryRepository,
)
from nerve_center.plugins.job_scout.discovery_loop import (
    MAX_REFERENCE_NETWORK_FETCH_ATTEMPTS,
    JobScoutDiscoveryLoop,
    _extract_employer_landscape_names,
    _extract_regional_alias_evidence,
)
from nerve_center.plugins.job_scout.market import MarketAlias
from nerve_center.plugins.job_scout.settings import JobScoutConfiguration


class _FixtureConnector:
    parser_version = "fixture-v1"

    def __init__(self, *, opening: bool = True) -> None:
        self.opening = opening
        self.calls: list[str] = []

    async def scan(
        self, company: Company, source: DiscoverySource, fetcher: Any
    ) -> ConnectorScanResult:
        if fetcher.before_request is not None:
            fetcher.before_request()
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


def test_shared_portal_company_is_not_seeded_for_employer_revisit(
    tmp_path: Path,
) -> None:
    loop, learning, companies, sources, *_rest = _build_loop(
        tmp_path,
        search=_FixtureSearch(),
    )
    company = companies.upsert(
        Company(
            id="shared-portal",
            canonical_name="Shared Portal",
            domain="public-careers.example",
        )
    )
    sources.upsert(
        DiscoverySource(
            id="portal-listing",
            company_id=company.id,
            name="Tenant listing",
            kind=SourceKind.JSON_LD,
            acquisition_class=AcquisitionClass.PUBLIC_HTML_ALLOWED,
            base_url="https://public-careers.example/careers/sample-city/jobs/123",
            configuration={
                "direct_employer_source": False,
                "source_role": "aggregator_listing",
            },
            parser_version="fixture-v1",
        )
    )

    loop._seed_known_company_strategies()

    assert all(
        item.dimensions.get("company_id") != company.id
        for item in learning.list_strategies()
    )


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
    assert cycle.useful_yield == 2
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
    assert cycle.coverage["search_requests_completed"] == 1
    assert cycle.coverage["search_results_returned"] == 10
    assert cycle.coverage["search_results_eligible"] == 6
    assert cycle.coverage["search_sources_registered"] == 6
    assert cycle.coverage["source_scans_attempted"] == 6
    assert cycle.coverage["source_scans_completed"] == 6
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
    assert len(anchors) == 20


def test_regional_alias_candidates_are_extracted_from_public_evidence() -> None:
    evidence = _extract_regional_alias_evidence(
        [
            SearchResult(
                title="Who We Are | Piedmont Triad Regional Council, NC",
                url="https://region.example/triad",
            ),
            SearchResult(
                title="About Research Triangle Regional Partnership",
                url="https://region.example/triangle",
            ),
            SearchResult(
                title="About Us - Research Triangle Regional Partnership",
                url="https://region.example/triangle/about",
            ),
            SearchResult(
                title="Unrelated private directory",
                url="https://directory.example/",
            ),
        ],
        anchor="Greensboro-High Point, NC",
    )

    assert [item["alias"] for item in evidence] == [
        "Piedmont Triad",
        "Research Triangle",
    ]
    assert all(item["url"].startswith("https://region.example/") for item in evidence)


def test_employer_names_are_extracted_from_structured_landscape_heading() -> None:
    names = _extract_employer_landscape_names(
        """
        <h2>Major Employers</h2>
        <h4>Example Systems</h4><li>Sample Health</li><td>Example Mobility</td>
        <h2>Economic Data</h2><h3>Not an employer</h3>
        """
    )

    assert names == [
        "Example Systems",
        "Sample Health",
        "Example Mobility",
    ]


def test_local_employer_landscape_creates_evidence_backed_deepening_searches(
    tmp_path: Path,
) -> None:
    class ReferenceSearch:
        async def search(self, _query: str) -> list[SearchResult]:
            return []

        async def search_references(self, _query: str) -> list[SearchResult]:
            return [
                SearchResult(
                    title="Major Employers | Example Region",
                    url="https://region.example.gov/employers",
                )
            ]

        async def fetch_reference(self, _url: str) -> str:
            return "<h2>Major Employers</h2><h4>Example Systems</h4><h2>Contact</h2>"

    loop, learning, *_rest = _build_loop(
        tmp_path,
        search=ReferenceSearch(),
        strategies_per_cycle=1,
    )
    landscape = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )

    outcome, requests, warnings = asyncio.run(
        loop._execute_public_search(landscape)
    )

    candidates = [
        item
        for item in learning.list_strategies()
        if item.dimensions.get("hypothesis_family") == "local_employer_deepen"
    ]
    assert warnings == []
    assert requests == 2
    assert outcome.detail["stages"]["reference_pages_inspected"] == 1
    assert outcome.detail["stages"]["employer_candidates_discovered"] == 1
    assert outcome.detail["stages"]["employer_reference_evidence"] == [
            {
                "url": "https://region.example.gov/employers",
                "requested_url": "https://region.example.gov/employers",
                "status": "inspected",
            "candidate_count": 1,
            "cache_status": "unavailable",
            "content_type": "text/html",
        }
    ]
    assert candidates[0].dimensions["anchor"] == "Example Systems"
    assert candidates[0].dimensions["employer_evidence_authority"] == "civic"
    assert candidates[0].dimensions["employer_evidence_revision"] == (
        EMPLOYER_LANDSCAPE_EVIDENCE_REVISION
    )
    assert candidates[0].dimensions["employer_evidence_url"] == (
        "https://region.example.gov/employers"
    )


def test_structured_public_directory_creates_only_evidence_backed_hypotheses(
    tmp_path: Path,
) -> None:
    class StructuredReferenceSearch:
        async def search(self, query: str) -> list[SearchResult]:
            return await self.search_references(query)

        async def search_references(self, _query: str) -> list[SearchResult]:
            return [
                SearchResult(
                    title="Regional employer directory",
                    url="https://data.example.gov/employers.json",
                )
            ]

        async def fetch_reference(self, url: str):  # type: ignore[no-untyped-def]
            from nerve_center.discovery.search import ReferenceDocument

            return ReferenceDocument(
                url=url,
                text=(
                    '[{"employer_name":"Example Mobility","employees":1200},'
                    '{"company_name":"Sample Semiconductor","employees":900}]'
                ),
                content_type="application/json",
                cache_status="hit",
            )

        def reference_cache_status(self, _url: str) -> str:
            return "hit"

    loop, learning, *_rest = _build_loop(
        tmp_path,
        search=StructuredReferenceSearch(),  # type: ignore[arg-type]
        strategies_per_cycle=1,
    )
    landscape = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )

    outcome, requests, warnings = asyncio.run(loop._execute_public_search(landscape))

    candidates = [
        item.dimensions["anchor"]
        for item in learning.list_strategies()
        if item.dimensions.get("hypothesis_family") == "local_employer_deepen"
    ]
    assert warnings == []
    assert requests == 1
    assert candidates == ["Example Mobility", "Sample Semiconductor"]
    assert outcome.detail["stages"]["reference_cache_hits"] == 1
    assert outcome.detail["stages"]["employer_candidates_discovered"] == 2


def test_common_employer_list_headings_create_bounded_hypotheses() -> None:
    ranked = _extract_employer_landscape_names(
        """
        <h2>Top 25 Private Employers</h2>
        <table><tr><td>Example Manufacturing</td></tr>
        <tr><td>Sample Health System</td></tr></table>
        <h2>Contact</h2>
        """
    )
    directory = _extract_employer_landscape_names(
        """
        <h2>Employer Directory</h2>
        <ul><li>Atlas Systems</li><li>Beacon Analytics</li></ul>
        <h2>Resources</h2>
        """
    )

    assert ranked == ["Example Manufacturing", "Sample Health System"]
    assert directory == ["Atlas Systems", "Beacon Analytics"]


def test_schema_org_organization_names_are_extracted_without_heading() -> None:
    names = _extract_employer_landscape_names(
        """
        <script type="application/ld+json">
        {"@type":"ItemList","itemListElement":[
          {"@type":"Organization","name":"Example Aerospace"},
          {"@type":"Corporation","name":"Sample Health"}
        ]}
        </script>
        """
    )

    assert names == ["Example Aerospace", "Sample Health"]


def test_schema_org_page_publisher_is_not_an_employer_directory() -> None:
    names = _extract_employer_landscape_names(
        """
        <script type="application/ld+json">
        {"@type":"Organization","name":"Example Chamber of Commerce"}
        </script>
        """
    )

    assert names == []


def test_deferred_reference_does_not_displace_an_eligible_directory(
    tmp_path: Path,
) -> None:
    class RetryAwareReferenceSearch:
        fetched: list[str] = []

        async def search(self, query: str) -> list[SearchResult]:
            return await self.search_references(query)

        async def search_references(self, _query: str) -> list[SearchResult]:
            return [
                SearchResult(
                    title="Invalid",
                    url="https://0-invalid.example.gov/employers",
                ),
                SearchResult(title="Deferred", url="https://a.example.gov/employers"),
                SearchResult(title="First", url="https://b.example.gov/employers"),
                SearchResult(title="Second", url="https://c.example.gov/employers"),
            ]

        def reference_cache_status(self, url: str) -> str:
            if "invalid.example" in url:
                return "invalid"
            return "retry_deferred" if "a.example" in url else "miss"

        async def fetch_reference(self, url: str) -> str:
            self.fetched.append(url)
            name = "First Systems" if "b.example" in url else "Second Systems"
            return f"<h2>Major Employers</h2><li>{name}</li><h2>Contact</h2>"

    search = RetryAwareReferenceSearch()
    loop, learning, *_rest = _build_loop(
        tmp_path,
        search=search,  # type: ignore[arg-type]
        strategies_per_cycle=1,
    )
    landscape = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )

    outcome, requests, _warnings = asyncio.run(loop._execute_public_search(landscape))

    assert search.fetched == [
        "https://b.example.gov/employers",
        "https://c.example.gov/employers",
    ]
    assert requests == 3
    assert outcome.detail["stages"]["reference_fetches_deferred"] == 1
    assert outcome.detail["stages"]["reference_pages_inspected"] == 2
    assert any(
        item["status"] == "invalid"
        for item in outcome.detail["stages"]["employer_reference_evidence"]
    )


def test_reference_network_failures_fall_through_only_to_explicit_cap(
    tmp_path: Path,
) -> None:
    class FailingReferenceSearch:
        fetched: list[str] = []

        async def search(self, query: str) -> list[SearchResult]:
            return await self.search_references(query)

        async def search_references(self, _query: str) -> list[SearchResult]:
            return [
                SearchResult(
                    title=f"Employer directory {index}",
                    url=f"https://region-{index}.example.gov/employers",
                )
                for index in range(6)
            ]

        def reference_cache_status(self, _url: str) -> str:
            return "miss"

        async def fetch_reference(self, url: str) -> str:
            self.fetched.append(url)
            raise SearchChallengeError("synthetic reference challenge")

    search = FailingReferenceSearch()
    loop, learning, *_rest = _build_loop(
        tmp_path,
        search=search,  # type: ignore[arg-type]
        strategies_per_cycle=1,
    )
    landscape = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Example, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )

    outcome, requests, _warnings = asyncio.run(loop._execute_public_search(landscape))

    stages = outcome.detail["stages"]
    assert len(search.fetched) == MAX_REFERENCE_NETWORK_FETCH_ATTEMPTS
    assert requests == 1 + MAX_REFERENCE_NETWORK_FETCH_ATTEMPTS
    assert stages["reference_network_fetches_attempted"] == (
        MAX_REFERENCE_NETWORK_FETCH_ATTEMPTS
    )
    assert sum(
        item["status"] == "network_fetch_cap"
        for item in stages["employer_reference_evidence"]
    ) == 3


def test_regional_alias_probe_creates_learned_role_searches(tmp_path: Path) -> None:
    class ReferenceSearch:
        async def search(self, _query: str) -> list[SearchResult]:
            return []

        async def search_references(self, _query: str) -> list[SearchResult]:
            return [
                SearchResult(
                    title="Piedmont Triad Regional Council",
                    url="https://region.example/triad",
                ),
                SearchResult(
                    title="Triangle J Council of Governments",
                    url="https://region.example/triangle-j",
                ),
            ]

    loop, learning, *_rest = _build_loop(
        tmp_path,
        search=ReferenceSearch(),
        strategies_per_cycle=1,
    )
    probe = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "regional_alias_probe",
            "anchor": "Greensboro-High Point, NC",
            "source_domain": "web",
        },
        origin="fixture",
    )

    outcome, requests, _warnings = asyncio.run(
        loop._execute_public_search(probe)
    )

    aliases = [
        item
        for item in learning.list_strategies()
        if item.dimensions.get("hypothesis_family") == "regional_alias"
    ]
    assert requests == 1
    assert outcome.detail["stages"]["regional_aliases_discovered"] == 2
    assert {item.dimensions["location"] for item in aliases} == {
        "Piedmont Triad",
        "Triangle J",
    }
    assert {item.dimensions["alias_provenance_url"] for item in aliases} == {
        "https://region.example/triad",
        "https://region.example/triangle-j",
    }


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

def test_employer_landscape_ignores_navigation_subheadings_and_social_links() -> None:
    names = _extract_employer_landscape_names(
        """
        <h1>Major Employers</h1>
        <h2>In this section</h2>
        <h2>Strategic Location</h2>
        <ul><li>Facebook</li><li>LinkedIn</li></ul>
        <table><tr><td>Example Systems</td></tr></table>
        <h1>Contact</h1>
        """
    )

    assert names == ["Example Systems"]

