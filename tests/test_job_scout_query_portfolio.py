import asyncio
from pathlib import Path
from types import SimpleNamespace

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    NormalizedJobOpening,
    SourceKind,
    WorkArrangement,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import CompanyRepository
from nerve_center.plugins.job_scout.discovery_learning import StrategyOutcome
from nerve_center.plugins.job_scout.discovery_quality import (
    DiscoveryQualityRepository,
    SourceAwareJobScoutDiscoveryLoop,
)
from nerve_center.plugins.job_scout.query_portfolio import (
    build_coverage_gap_profile,
    build_query_portfolio,
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
        locations=["Greensboro, NC"],
        source_domains=["job-boards.greenhouse.io"],
        limit=60,
    )
    families = {item["hypothesis_family"] for item in portfolio}
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

    assert {"direct_role", "adjacent_role", "seniority_variant"}.issubset(families)
    identities = {(item.source_path, item.query.casefold()) for item in compiled}
    assert len(identities) == len(compiled)
    greenhouse = [
        item
        for dimensions, item in zip(portfolio, compiled, strict=True)
        if dimensions["source_domain"] == "job-boards.greenhouse.io"
    ]
    assert greenhouse
    assert all("Greensboro" not in item.query for item in greenhouse)
    assert all(item.source_path == "structured_ats_xray" for item in greenhouse)
    assert source_capabilities("builtin.com").include_location is True


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
