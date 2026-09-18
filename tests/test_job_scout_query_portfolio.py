import asyncio
from pathlib import Path
from types import SimpleNamespace

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    SourceHealth,
    SourceKind,
    WorkArrangement,
)
from nerve_center.discovery.search import SearchResult, UrlClassification
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import CompanyRepository
from nerve_center.plugins.job_scout.discovery_learning import StrategyOutcome
from nerve_center.plugins.job_scout.discovery_loop import _RequestAllowance
from nerve_center.plugins.job_scout.discovery_quality import (
    DiscoveryQualityRepository,
    SourceAwareJobScoutDiscoveryLoop,
    _CompiledQueryAdapter,
)
from nerve_center.plugins.job_scout.market import MarketAlias
from nerve_center.plugins.job_scout.query_portfolio import (
    build_coverage_gap_profile,
    build_query_portfolio,
    compile_employer_deepening_queries,
    compile_strategy_query,
    source_capabilities,
)
from nerve_center.plugins.job_scout.settings import JobScoutConfiguration


def _database(tmp_path: Path) -> Database:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    return database


def test_portfolio_compiles_materially_distinct_source_aware_families() -> None:
    portfolio = build_query_portfolio(
        target_titles=["Director of Product Management"],
        keywords=["data analytics", "workflow automation", "healthcare technology"],
        locations=["Greensboro, NC", "Winston-Salem, NC", "Raleigh, NC"],
        source_domains=[
            "indeed.com",
            "job-boards.greenhouse.io",
            "jobs.lever.co",
        ],
        limit=16,
    )
    families = {item["hypothesis_family"] for item in portfolio}
    domains = {item["source_domain"] for item in portfolio}
    compiled = [
        compile_strategy_query(
            item,
            evidence_terms=[
                "Director of Product Management",
                "data analytics",
                "workflow automation",
                "healthcare technology",
            ],
        )
        for item in portfolio
    ]

    assert {
        "direct_role",
        "adjacent_role",
        "seniority_variant",
        "domain_capability",
    }.issubset(families)
    assert {
        "web",
        "indeed.com",
        "job-boards.greenhouse.io",
        "jobs.lever.co",
    }.issubset(domains)
    identities = {(item.source_path, item.query.casefold()) for item in compiled}
    assert len(identities) == len(compiled)
    greenhouse = [
        item
        for dimensions, item in zip(portfolio, compiled, strict=True)
        if dimensions["source_domain"] == "job-boards.greenhouse.io"
    ]
    assert greenhouse
    assert all("Greensboro" not in item.query for item in greenhouse)
    assert all("jobs careers" not in item.query for item in greenhouse)
    assert all(item.source_path == "structured_ats_xray" for item in greenhouse)
    broad = next(
        item
        for dimensions, item in zip(portfolio, compiled, strict=True)
        if dimensions["source_domain"] == "web"
    )
    assert "Greensboro" in broad.query
    assert "jobs careers" in broad.query
    assert source_capabilities("indeed.com").include_location is True
    assert not any(
        item["hypothesis_family"] == "local_employer" for item in portfolio
    )


def test_capability_phrase_is_not_invented_as_employer_archetype() -> None:
    portfolio = build_query_portfolio(
        target_titles=["Director of Product Management"],
        keywords=["Human-Centered Design", "analytics"],
        locations=["Greensboro, NC"],
        source_domains=[],
        limit=24,
    )

    assert any(
        item["hypothesis_family"] == "domain_capability"
        and item["anchor"] == "Human-Centered Design"
        for item in portfolio
    )
    assert not any(
        item.get("employer_archetype") == "Human-Centered Design company"
        or item.get("anchor") == "Human-Centered Design company"
        for item in portfolio
    )


def test_bounded_portfolio_rotates_starting_market_across_source_buckets() -> None:
    locations = [f"Market {index}, NC" for index in range(12)]
    portfolio = build_query_portfolio(
        target_titles=["Product Manager"],
        keywords=["analytics", "workflow automation", "healthcare technology"],
        locations=locations,
        source_domains=["indeed.com", "jobs.example.com", "careers.example.org"],
        limit=24,
    )

    represented = {item.get("location", "") for item in portfolio}

    assert len(represented) >= 6
    assert any(item in represented for item in locations[6:])


def test_market_strategies_cover_employment_centers_and_region_alias_probes(
    tmp_path: Path,
) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    loop = object.__new__(SourceAwareJobScoutDiscoveryLoop)
    loop.learning = learning

    loop._seed_market_strategies([
        MarketAlias(
            "Greensboro, NC", "configured", 0, "configured_starting_location"
        ),
        MarketAlias(
            "Durham, NC", "metro_core", 50, "census_2025_gazetteer_cbsa_core_place"
        ),
        MarketAlias(
            "Durham-Chapel Hill, NC",
            "metro_alias",
            50,
            "census_2025_gazetteer_nearest_cbsa",
        ),
    ])

    strategies = learning.list_strategies()
    local_locations = {
        item.dimensions.get("location")
        for item in strategies
        if item.dimensions.get("hypothesis_family") == "local_employer"
    }
    probes = [
        item
        for item in strategies
        if item.dimensions.get("hypothesis_family") == "regional_alias_probe"
    ]

    assert {"Greensboro, NC", "Durham, NC"}.issubset(local_locations)
    durham = next(
        item
        for item in strategies
        if item.dimensions.get("hypothesis_family") == "local_employer"
        and item.dimensions.get("location") == "Durham, NC"
        and item.dimensions.get("anchor") == "major employers"
    )
    assert durham.dimensions["market_kind"] == "metro_core"
    assert durham.dimensions["market_distance_miles"] == "50.0"
    assert durham.dimensions["market_rank"] == "1"
    assert durham.dimensions["query_revision"] == "market_reference_v6"
    landscape_query = compile_strategy_query(durham.dimensions)
    assert landscape_query.source_path == "broad_web_reference"
    assert landscape_query.query == 'Durham NC "major employers"'
    assert "chamber" not in landscape_query.query
    assert "economic development" not in landscape_query.query
    local_queries = {
        item.dimensions["anchor"]: compile_strategy_query(item.dimensions).query
        for item in strategies
        if item.dimensions.get("hypothesis_family") == "local_employer"
        and item.dimensions.get("location") == "Durham, NC"
    }
    assert local_queries == {
        "major employers": 'Durham NC "major employers"',
        "largest employers": 'Durham NC "largest employers"',
        "top employers": 'Durham NC "top employers"',
        "employer directory": 'Durham NC "employer directory"',
        "company headquarters": 'Durham NC "company headquarters"',
    }
    assert [item.dimensions["anchor"] for item in probes] == [
        "Durham-Chapel Hill, NC"
    ]
    regional_query = compile_strategy_query(probes[0].dimensions)
    assert regional_query.query == (
        'Durham Chapel Hill NC "regional council" OR '
        '"regional partnership" OR "council of governments"'
    )
    assert all("volvo" not in str(item.dimensions).casefold() for item in strategies)
    assert all("wolfspeed" not in str(item.dimensions).casefold() for item in strategies)


def test_local_employer_deepening_resolves_career_surface_before_location() -> None:
    compiled = compile_strategy_query(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer_deepen",
            "anchor": "Atrium Health Wake ForestBaptist HighPoint Medical Center",
            "location": "Greensboro-High Point, NC Metro Area",
            "source_domain": "web",
        }
    )

    assert compiled.valid is True
    assert compiled.source_path == "broad_web"
    assert compiled.query == (
        '"Atrium Health Wake Forest Baptist High Point Medical Center" careers'
    )
    assert "Greensboro" not in compiled.query
    assert "jobs careers" not in compiled.query
    assert "location_deferred_to_employer_validation" in compiled.warnings


def test_local_employer_deepening_has_bounded_canonical_career_failbacks() -> None:
    queries = compile_employer_deepening_queries(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer_deepen",
            "anchor": "ExampleMobility",
            "location": "First Market, NC",
            "source_domain": "web",
        }
    )

    assert [item.query for item in queries] == [
        '"Example Mobility" careers',
        '"Example Mobility" official careers',
        '"Example Mobility" employment opportunities',
    ]


def test_employer_query_failback_stops_at_first_direct_career_result() -> None:
    class Search:
        async def search(self, query: str) -> list[SearchResult]:
            if query.endswith('" careers'):
                return [
                    SearchResult(
                        title="Example jobs on a board",
                        url="https://jobs.example.net/example",
                        classification=UrlClassification.MAJOR_JOB_BOARD,
                    )
                ]
            return [
                SearchResult(
                    title="Example Mobility Careers",
                    url="https://example.test/careers",
                    classification=UrlClassification.COMPANY_CAREER,
                )
            ]

    allowance = _RequestAllowance(limit=3)
    allowance.reserve()
    adapter = _CompiledQueryAdapter(
        Search(),
        ('"Example Mobility" careers', '"Example Mobility" official careers'),
        allowance,
    )

    results = asyncio.run(adapter.search("ignored"))

    assert results[0].url == "https://example.test/careers"
    assert adapter.queries_attempted == [
        '"Example Mobility" careers',
        '"Example Mobility" official careers',
    ]
    assert adapter.search_requests_completed == 2
    assert adapter.failbacks_used == 1
    assert adapter.failback_reason == "empty_or_no_direct_employer_result"
    assert allowance.used == 2


def test_query_linter_rejects_contradictions_and_unsupported_requirements() -> None:
    contradictory = compile_strategy_query(
        {
            "kind": "public_search",
            "anchor": "Product Manager",
            "exclude": "manager",
            "source_domain": "web",
        },
        evidence_terms=["Product Manager", "analytics"],
    )
    invented = compile_strategy_query(
        {
            "kind": "public_search",
            "anchor": "Product Manager",
            "technology": "quantum kubernetes",
            "source_domain": "web",
        },
        evidence_terms=["Product Manager", "analytics"],
    )
    catch_all = compile_strategy_query(
        {"kind": "public_search", "anchor": "Director", "source_domain": "web"},
        evidence_terms=["Director of Product"],
    )

    assert contradictory.valid is False
    assert "contradictory_exclusion:manager" in contradictory.warnings
    assert invented.valid is False
    assert invented.warnings == ("unsupported_technology",)
    assert catch_all.valid is False
    assert catch_all.warnings == ("catch_all_anchor",)


def test_reflection_semantics_reject_low_intent_and_preserve_adjacent_roles() -> None:
    evidence = [
        "Director of Product Management",
        "Human-Centered Design",
        "analytics",
    ]
    malformed_local = compile_strategy_query(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "Human-Centered Design company",
            "location": "High Point, NC",
            "source_domain": "web",
        },
        evidence_terms=evidence,
    )
    internship = compile_strategy_query(
        {
            "kind": "public_search",
            "hypothesis_family": "adjacent_role",
            "anchor": "Human-Centered Design Intern",
            "source_domain": "web",
        },
        evidence_terms=evidence,
    )
    workshop = compile_strategy_query(
        {
            "kind": "public_search",
            "hypothesis_family": "gap_reflection",
            "anchor": "Design Thinking Workshop",
            "source_domain": "web",
        },
        evidence_terms=evidence,
    )
    adjacent = compile_strategy_query(
        {
            "kind": "public_search",
            "hypothesis_family": "adjacent_role",
            "anchor": "Senior UX Researcher",
            "source_domain": "web",
        },
        evidence_terms=evidence,
    )

    assert malformed_local.valid is False
    assert malformed_local.warnings == ("unsupported_local_employer_anchor",)
    assert internship.valid is False
    assert internship.warnings == ("seniority_mismatch",)
    assert workshop.valid is False
    assert workshop.warnings == ("non_role_activity_anchor",)
    assert adjacent.valid is True


class _NoNetworkSearch:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, _query: str) -> list[object]:
        self.calls += 1
        return []


class _ConfigStore:
    def load(self) -> JobScoutConfiguration:
        return JobScoutConfiguration(
            target_titles=["Product Manager"],
            locations=["Greensboro, NC"],
            remote_preference="remote",
            manual_keywords=["analytics"],
            public_job_boards=[],
        )


class _Coordinator:
    def __init__(self) -> None:
        self.store = _ConfigStore()

    def _discover_keywords(self, _configuration: JobScoutConfiguration) -> SimpleNamespace:
        return SimpleNamespace(keywords=["analytics"])


def test_invalid_strategy_is_rejected_before_network_request() -> None:
    loop = object.__new__(SourceAwareJobScoutDiscoveryLoop)
    loop.coordinator = _Coordinator()
    loop.search_adapter = _NoNetworkSearch()
    strategy = SimpleNamespace(
        dimensions={
            "kind": "public_search",
            "anchor": "Product Manager",
            "exclude": "manager",
            "source_domain": "web",
        }
    )

    outcome, requests, warnings = asyncio.run(loop._execute_public_search(strategy))

    assert outcome.status == "rejected"
    assert requests == 0
    assert loop.search_adapter.calls == 0
    assert "contradictory_exclusion:manager" in warnings


def test_cross_strategy_convergence_promotes_deepening_not_fit(tmp_path: Path) -> None:
    database = _database(tmp_path)
    CompanyRepository(database).upsert(
        Company(id="company-1", canonical_name="Example Co", domain="example.com")
    )
    learning = DiscoveryQualityRepository(database)
    revisit = learning.ensure_strategy(
        {"kind": "company_revisit", "company_id": "company-1"},
        origin="known_company",
    )
    first = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "direct_role",
            "anchor": "Product Manager",
        },
        origin="test",
    )
    second = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "domain_capability",
            "anchor": "analytics",
        },
        origin="test",
    )

    learning.record_company_evidence("company-1", first.id)
    assert learning.get_strategy(revisit.id).learned_weight == 1.0
    learning.record_company_evidence("company-1", second.id)

    assert learning.get_strategy(revisit.id).learned_weight > 1.0


def test_strategy_attempt_audit_records_weight_movement(tmp_path: Path) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    strategy = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "direct_role",
            "anchor": "Product Manager",
            "source_domain": "web",
        },
        origin="test",
    )

    result = learning.record_attempt(
        "run-1",
        1,
        strategy.id,
        "deepen",
        StrategyOutcome(results_examined=4, companies_discovered=1),
    )
    row = next(
        item
        for item in learning.discovery_audit()["strategies"]
        if item["id"] == strategy.id
    )

    assert row["weight_before"] == 1.0
    assert row["weight_after"] == round(result.learned_weight, 3)
    assert row["weight_after"] > row["weight_before"]
    assert row["family_id"] == strategy.family_id
    assert row["family_weight_before"] == 1.0
    assert row["family_weight_after"] is not None
    family = next(
        item for item in learning.discovery_audit()["strategy_families"]
        if item["id"] == strategy.family_id
    )
    assert family["attempts"] == 1


def test_structured_refresh_gets_one_time_initial_preference(tmp_path: Path) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    strategy = learning.ensure_strategy(
        {"kind": "source_revisit", "source_id": "greenhouse-1"},
        origin="known_source",
    )

    learning.promote_initial_structured_refresh(strategy.id)
    promoted = learning.get_strategy(strategy.id)
    assert promoted.learned_weight == 1.35

    learning.record_attempt("run-1", 1, strategy.id, "deepen", StrategyOutcome())
    learned = learning.get_strategy(strategy.id)
    learning.promote_initial_structured_refresh(strategy.id, floor=1.8)
    assert learning.get_strategy(strategy.id).learned_weight == learned.learned_weight


def test_due_structured_source_is_preferred_through_real_seeding_path(tmp_path: Path) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    source = DiscoverySource(
        id="greenhouse-1",
        company_id="company-1",
        name="Example Greenhouse",
        kind=SourceKind.GREENHOUSE,
        acquisition_class=AcquisitionClass.PUBLIC_STRUCTURED_FEED,
        base_url="https://job-boards.greenhouse.io/example",
        parser_version="greenhouse-v1",
    )
    loop = object.__new__(SourceAwareJobScoutDiscoveryLoop)
    loop.learning = learning
    loop.sources = SimpleNamespace(list_due=lambda: [source])

    loop._seed_due_source_strategies()

    strategy = next(
        item
        for item in learning.list_strategies()
        if item.dimensions.get("source_id") == source.id
    )
    assert strategy.learned_weight == 1.35


def test_unhealthy_structured_source_gets_no_initial_priority_bonus(tmp_path: Path) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    source = DiscoverySource(
        id="greenhouse-degraded",
        company_id="company-1",
        name="Degraded Greenhouse",
        kind=SourceKind.GREENHOUSE,
        acquisition_class=AcquisitionClass.PUBLIC_STRUCTURED_FEED,
        base_url="https://job-boards.greenhouse.io/degraded",
        parser_version="greenhouse-v1",
        health=SourceHealth.DEGRADED,
    )
    loop = object.__new__(SourceAwareJobScoutDiscoveryLoop)
    loop.learning = learning
    loop.sources = SimpleNamespace(list_due=lambda: [source])

    loop._seed_due_source_strategies()

    strategy = next(
        item
        for item in learning.list_strategies()
        if item.dimensions.get("source_id") == source.id
    )
    assert strategy.learned_weight == 1.0


def test_stale_invented_archetype_does_not_perpetuate_coverage_gap(
    tmp_path: Path,
) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "employer_archetype",
            "anchor": "Product Manager",
            "employer_archetype": "Human-Centered Design company",
            "source_domain": "web",
        },
        origin="llm_gap_reflection",
    )

    gaps = build_coverage_gap_profile(
        target_titles=["Director of Product Management"],
        keywords=["Human-Centered Design", "analytics"],
        locations=[],
        remote_preference="any",
        strategies=learning.list_strategies(),
        openings=[],
        sources=[],
    )

    assert "employer_archetype" not in gaps


def test_reflection_result_rejects_low_intent_strategies_before_persistence(
    tmp_path: Path,
) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    learning.record_reflection_request("request-1", "run-1", 1)
    store = SimpleNamespace(
        load=lambda: JobScoutConfiguration(
            target_titles=["Director of Product Management"],
            locations=["Greensboro, NC"],
            remote_preference="remote",
            manual_keywords=["Human-Centered Design", "analytics"],
            public_job_boards=[],
        )
    )
    loop = object.__new__(SourceAwareJobScoutDiscoveryLoop)
    loop.learning = learning
    loop.coordinator = SimpleNamespace(
        store=store,
        _discover_keywords=lambda _configuration: SimpleNamespace(
            keywords=["Human-Centered Design", "analytics"]
        ),
    )

    created = loop.apply_reflection_result(
        "request-1",
        {
            "strategies": [
                {
                    "hypothesis_family": "adjacent_role",
                    "anchor": "Human-Centered Design Intern",
                    "source_domain": "web",
                    "rationale": "Explore internships.",
                },
                {
                    "hypothesis_family": "gap_reflection",
                    "anchor": "Design Thinking Workshop",
                    "source_domain": "web",
                    "rationale": "Explore workshops.",
                },
                {
                    "hypothesis_family": "employer_archetype",
                    "anchor": "Product Manager",
                    "employer_archetype": "Human-Centered Design company",
                    "source_domain": "web",
                    "rationale": "Treat the capability as a company class.",
                },
            ]
        },
    )

    assert created == 0
    assert not [
        item
        for item in learning.list_strategies()
        if item.origin == "llm_gap_reflection"
    ]
    assert learning.reflection_request("request-1")["status"] == "applied"


def test_coverage_gaps_are_explicit_and_bounded(tmp_path: Path) -> None:
    database = _database(tmp_path)
    learning = DiscoveryQualityRepository(database)
    strategy = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "direct_role",
            "anchor": "Director of Product Management",
            "source_domain": "web",
        },
        origin="test",
    )
    learning.record_attempt("run-1", 1, strategy.id, "deepen", StrategyOutcome())
    opening = NormalizedJobOpening(
        id="job-1",
        company_id="company-1",
        company_name="Example Co",
        company_domain="example.com",
        title="Software Engineer",
        description="Build billing systems.",
        location_text="Minneapolis, MN",
        work_arrangement=WorkArrangement.ON_SITE,
        source_url="https://example.com/jobs/1",
        canonical_url="https://example.com/jobs/1",
        provenance=[
            JobProvenance(
                source_id="source-1",
                connector="fixture",
                parser_version="fixture-v1",
                source_url="https://example.com/jobs/1",
                direct_employer_source=True,
            )
        ],
    )
    source = DiscoverySource(
        id="source-1",
        company_id="company-1",
        name="Example careers",
        kind=SourceKind.JSON_LD,
        acquisition_class=AcquisitionClass.PUBLIC_HTML_ALLOWED,
        base_url="https://example.com/careers",
        parser_version="fixture-v1",
    )

    gaps = build_coverage_gap_profile(
        target_titles=["Director of Product Management"],
        keywords=["analytics", "healthcare"],
        locations=["Greensboro, NC"],
        remote_preference="remote",
        strategies=learning.list_strategies(),
        openings=[opening],
        sources=[source],
    )

    assert gaps["role"] == ["Director of Product Management"]
    assert "analytics" in gaps["domain_capability"]
    assert gaps["geography"] == ["Greensboro, NC"]
    assert gaps["work_arrangement"] == ["remote"]
    assert "direct_role" in gaps["query_family"]


def test_reflection_work_is_explicitly_gap_driven(tmp_path: Path) -> None:
    learning = DiscoveryQualityRepository(_database(tmp_path))
    learning.update_session("run-1", phase="reflect", cycle=3)
    loop = object.__new__(SourceAwareJobScoutDiscoveryLoop)
    loop.learning = learning
    loop.coordinator = _Coordinator()
    loop.jobs = SimpleNamespace(list=lambda active_only=False: [])
    loop.sources = SimpleNamespace(list=lambda: [])

    work = loop.reflection_work_request("run-1", 3)

    assert (
        work["requirements"]["contract_version"]
        == "job-scout-discovery-reflection-v3"
    )
    assert "Coverage gaps:" in work["payload"]["user_prompt"]
    assert "Greensboro, NC" in work["payload"]["user_prompt"]
    assert "remote" in work["payload"]["user_prompt"]
    assert learning.session("run-1").coverage["coverage_gaps"]
