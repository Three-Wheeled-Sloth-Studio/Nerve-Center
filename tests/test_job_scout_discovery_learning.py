from datetime import UTC, datetime, timedelta
from pathlib import Path

from nerve_center.applications.models import ApplicationStatus, ApplicationUpdate
from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    SourceKind,
)
from nerve_center.persistence.applications import ApplicationRepository
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.plugins.job_scout.discovery_learning import (
    JobScoutDiscoveryRepository,
    StrategyOutcome,
)


def _database(tmp_path: Path) -> Database:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    return database


def test_strategy_identity_weighting_and_exploration_floor_are_durable(tmp_path: Path) -> None:
    database = _database(tmp_path)
    learning = JobScoutDiscoveryRepository(database)
    productive = learning.ensure_strategy(
        {"kind": "public_search", "title": "Product Manager", "location": "Greensboro, NC"},
        origin="profile",
    )
    novel = learning.ensure_strategy(
        {"kind": "public_search", "title": "Platform Lead", "location": "Winston-Salem, NC"},
        origin="profile",
    )

    productive = learning.record_attempt(
        "prior-run",
        1,
        productive.id,
        "expand",
        StrategyOutcome(
            results_examined=12,
            companies_discovered=2,
            career_sources_resolved=2,
            postings_inspected=5,
            opportunities_retained=2,
        ),
    )

    selected = learning.select_strategies(
        "current-run", limit=2, exploration_floor=0.5
    )
    assert {item.id for item in selected} == {productive.id, novel.id}
    assert productive.learned_weight > 1.0
    assert learning.ensure_strategy(
        {"location": "greensboro, nc", "title": "product manager", "kind": "public_search"},
        origin="reflection",
    ).id == productive.id

    restarted = JobScoutDiscoveryRepository(database)
    saved = restarted.get_strategy(productive.id)
    assert saved.attempts == 1
    assert saved.opportunities_retained == 2
    assert saved.learned_weight == productive.learned_weight


def test_source_count_without_posting_yield_is_not_rewarded(tmp_path: Path) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    strategy = learning.ensure_strategy(
        {"kind": "company_revisit", "company_id": "editorial-site"},
        origin="fixture",
        base_weight=1.45,
    )

    result = learning.record_attempt(
        "run-1",
        1,
        strategy.id,
        "deepen",
        StrategyOutcome(career_sources_resolved=250),
    )

    assert result.learned_weight < strategy.learned_weight
    assert result.last_productive_at is None


def test_strategy_selection_reserves_company_deepening_capacity(tmp_path: Path) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    for index in range(8):
        learning.ensure_strategy(
            {"kind": "public_search", "anchor": f"product {index}"},
            origin="profile",
        )
    company = learning.ensure_strategy(
        {"kind": "company_revisit", "company_id": "company-1"},
        origin="known_company",
    )

    selected = learning.select_strategies("run-1", limit=4, exploration_floor=0.25)

    assert company.id in {item.id for item in selected}


def test_strategy_selection_reserves_local_employer_exploration_capacity(
    tmp_path: Path,
) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    for index in range(8):
        learning.ensure_strategy(
            {"kind": "public_search", "anchor": f"product {index}"},
            origin="profile",
        )
    company = learning.ensure_strategy(
        {"kind": "company_revisit", "company_id": "company-1"},
        origin="known_company",
    )
    local = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "healthcare technology",
            "location": "Greensboro, NC",
            "source_domain": "web",
        },
        origin="source_aware_portfolio",
    )

    selected = learning.select_strategies("run-1", limit=4, exploration_floor=0.25)
    selected_ids = {item.id for item in selected}

    assert company.id in selected_ids
    assert local.id in selected_ids


def test_strategy_selection_reserves_civic_attachment_employer_deepening(
    tmp_path: Path,
) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    for index in range(12):
        learning.ensure_strategy(
            {"kind": "public_search", "anchor": f"product {index}"},
            origin="profile",
            base_weight=4.0,
        )
    learning.ensure_strategy(
        {"kind": "company_revisit", "company_id": "company-1"},
        origin="known_company",
    )
    learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Greensboro, NC",
            "source_domain": "web",
        },
        origin="market",
    )
    attachment_employer = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer_deepen",
            "anchor": "Atlas Lantern Works",
            "location": "Greensboro, NC",
            "source_domain": "web",
            "employer_evidence_authority": "civic_attachment",
        },
        origin="public_employer_attachment_evidence",
        base_weight=0.2,
    )

    selected = learning.select_strategies("run-1", limit=4, exploration_floor=0.25)

    assert attachment_employer.id in {item.id for item in selected}


def test_strategy_selection_deduplicates_civic_employer_query_across_markets(
    tmp_path: Path,
) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    for index in range(8):
        learning.ensure_strategy(
            {"kind": "public_search", "anchor": f"product {index}"},
            origin="profile",
        )
    first = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer_deepen",
            "anchor": "ExampleMobility",
            "location": "First City, NC",
            "source_domain": "web",
            "employer_evidence_authority": "civic_attachment",
        },
        origin="public_employer_attachment_evidence",
    )
    duplicate = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer_deepen",
            "anchor": "Example Mobility",
            "location": "First Metro Area",
            "source_domain": "web",
            "employer_evidence_authority": "civic",
        },
        origin="public_employer_landscape_evidence",
    )

    selected = learning.select_strategies("run-1", limit=4, exploration_floor=0.25)
    selected_ids = {item.id for item in selected}

    assert first.id in selected_ids
    assert duplicate.id not in selected_ids

    learning.record_attempt("run-1", 1, first.id, "deepen", StrategyOutcome())
    selected_again = learning.select_strategies(
        "run-1", limit=4, exploration_floor=0.25
    )

    assert duplicate.id not in {item.id for item in selected_again}


def test_market_exploration_covers_distinct_locations_and_regional_probe(
    tmp_path: Path,
) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    for index in range(8):
        learning.ensure_strategy(
            {"kind": "public_search", "anchor": f"product {index}"},
            origin="profile",
        )
    company = learning.ensure_strategy(
        {"kind": "company_revisit", "company_id": "company-1"},
        origin="known_company",
    )
    first_market = [
        learning.ensure_strategy(
            {
                "kind": "public_search",
                "hypothesis_family": "local_employer",
                "anchor": anchor,
                "location": "First Market, NC",
                "source_domain": "web",
                "market_kind": "configured",
                "market_rank": "0",
            },
            origin="market",
        )
        for anchor in ("major employers", "company headquarters")
    ]
    adjacent = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Adjacent Core, NC",
            "source_domain": "web",
            "market_kind": "metro_core",
            "market_rank": "4",
        },
        origin="market",
    )
    regional = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "regional_alias_probe",
            "anchor": "Adjacent Metro, NC Metro Area",
            "source_domain": "web",
            "market_kind": "metro_alias",
            "market_rank": "3",
        },
        origin="market",
    )
    learning.record_attempt(
        "prior-run",
        1,
        first_market[0].id,
        "expand",
        StrategyOutcome(companies_discovered=1),
    )

    selected = learning.select_strategies("run-1", limit=4, exploration_floor=0.25)
    selected_ids = {item.id for item in selected}

    assert company.id in selected_ids
    assert adjacent.id in selected_ids
    assert regional.id in selected_ids
    assert first_market[1].id not in selected_ids


def test_market_exploration_prefers_current_query_revision(tmp_path: Path) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    for index in range(8):
        learning.ensure_strategy(
            {"kind": "public_search", "anchor": f"product {index}"},
            origin="profile",
        )
    stale = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Stale Market, NC",
            "source_domain": "web",
            "market_rank": "0",
            "query_revision": "market_reference_v2",
        },
        origin="market",
    )
    current = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Current Market, NC",
            "source_domain": "web",
            "market_rank": "1",
            "query_revision": "market_reference_v5",
        },
        origin="market",
    )

    selected = learning.select_strategies("run-1", limit=4, exploration_floor=0.25)
    selected_ids = {item.id for item in selected}

    assert current.id in selected_ids
    assert stale.id not in selected_ids


def test_current_market_attempt_moves_selection_to_next_market(tmp_path: Path) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    first = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "First Market, NC",
            "source_domain": "web",
            "market_rank": "0",
            "query_revision": "market_reference_v5",
        },
        origin="market",
    )
    learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "company headquarters",
            "location": "First Market, NC",
            "source_domain": "web",
            "market_rank": "0",
            "query_revision": "market_reference_v5",
        },
        origin="market",
    )
    second = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "local_employer",
            "anchor": "major employers",
            "location": "Second Market, NC",
            "source_domain": "web",
            "market_rank": "1",
            "query_revision": "market_reference_v5",
        },
        origin="market",
    )
    learning.record_attempt(
        "prior-run", 1, first.id, "expand", StrategyOutcome(companies_discovered=1)
    )

    selected = learning.select_strategies("run-1", limit=4, exploration_floor=0.25)

    assert second.id in {item.id for item in selected}


def test_location_strategy_family_accumulates_zero_yield_across_query_variants(
    tmp_path: Path,
) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    variants = [
        learning.ensure_strategy(
            {
                "kind": "public_search",
                "hypothesis_family": "direct_role",
                "anchor": anchor,
                "source_domain": "web",
                "source_path": "broad_web",
                "location": "Greensboro, NC",
            },
            origin="fixture",
        )
        for anchor in ("Product Manager", "Digital Product Lead")
    ]
    assert variants[0].family_id == variants[1].family_id

    for cycle, strategy in enumerate(variants, start=1):
        learning.record_attempt(
            "prior-run",
            cycle,
            strategy.id,
            "deepen",
            StrategyOutcome(
                companies_discovered=1,
                career_sources_resolved=1,
                opportunities_retained=0,
            ),
        )

    family = next(
        item for item in learning.list_strategy_families()
        if item.id == variants[0].family_id
    )
    assert family.attempts == 2
    assert family.companies_discovered == 2
    assert family.career_sources_resolved == 2
    assert family.opportunities_retained == 0
    assert family.learned_weight == 0.84
    assert family.influence == "deprioritized"

    productive = learning.ensure_strategy(
        {
            "kind": "public_search",
            "hypothesis_family": "direct_role",
            "anchor": "Product Manager",
            "source_domain": "web",
            "source_path": "broad_web",
            "location": "Raleigh, NC",
        },
        origin="fixture",
    )
    learning.record_attempt(
        "prior-run",
        3,
        productive.id,
        "deepen",
        StrategyOutcome(opportunities_retained=1),
    )

    selected = learning.select_strategies(
        "current-run",
        limit=1,
        exploration_floor=0,
    )
    assert selected[0].id == productive.id


def test_cooldown_survives_restart_and_run_changes(tmp_path: Path) -> None:
    database = _database(tmp_path)
    learning = JobScoutDiscoveryRepository(database)
    strategy = learning.ensure_strategy(
        {"kind": "public_search", "anchor": "Product"}, origin="fixture",
    )
    now = datetime.now(UTC)
    learning.record_attempt("run-1", 1, strategy.id, "expand", StrategyOutcome(),
                            finished_at=now)
    restarted = JobScoutDiscoveryRepository(database)
    assert restarted.select_strategies(
        "run-2", revisit_after_seconds=86400, now=now + timedelta(hours=1),
    ) == []
    assert restarted.select_strategies(
        "run-1", revisit_after_seconds=86400, now=now + timedelta(days=1),
    )[0].id == strategy.id


def test_company_is_retained_as_strategy_evidence_with_zero_openings(tmp_path: Path) -> None:
    database = _database(tmp_path)
    companies = CompanyRepository(database)
    learning = JobScoutDiscoveryRepository(database)
    companies.upsert(
        Company(
            id="company-1",
            canonical_name="Example Co",
            domain="example.com",
        )
    )
    strategy = learning.ensure_strategy(
        {"kind": "company_revisit", "company": "example.com"},
        origin="local_market",
    )

    learning.record_company_evidence(
        "company-1",
        strategy.id,
        location_alias="Greensboro, NC",
        provenance={"reason": "plausible local employer"},
        openings_seen=0,
    )

    assert learning.company_evidence_count("company-1") == 1
    assert JobScoutDiscoveryRepository(database).company_evidence_count("company-1") == 1


def test_application_feedback_updates_discovery_strategy_without_ranking_mutation(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    applications = ApplicationRepository(database)
    learning = JobScoutDiscoveryRepository(database)
    strategy = learning.ensure_strategy(
        {"kind": "public_search", "title": "Product Manager", "location": "Greensboro, NC"},
        origin="profile",
    )
    companies.upsert(
        Company(
            id="company-1",
            canonical_name="Example Co",
            domain="example.com",
        )
    )
    sources.upsert(
        DiscoverySource(
            id="source-1",
            company_id="company-1",
            name="Example careers",
            kind=SourceKind.JSON_LD,
            acquisition_class=AcquisitionClass.PUBLIC_HTML_ALLOWED,
            base_url="https://example.com/careers",
            configuration={"discovery_strategy_ids": [strategy.id]},
            parser_version="jsonld-v1",
        )
    )
    discovered = datetime.now(UTC)
    jobs.upsert(
        NormalizedJobOpening(
            id="job-1",
            company_id="company-1",
            company_name="Example Co",
            company_domain="example.com",
            title="Product Manager",
            description="Own a data product.",
            location_text="Greensboro, NC",
            source_url="https://example.com/jobs/1",
            canonical_url="https://example.com/jobs/1",
            discovered_at=discovered,
            provenance=[
                JobProvenance(
                    source_id="source-1",
                    connector="json_ld",
                    parser_version="jsonld-v1",
                    source_url="https://example.com/jobs/1",
                    direct_employer_source=True,
                    discovered_at=discovered,
                )
            ],
        )
    )
    before = learning.get_strategy(strategy.id)
    applications.save(
        "job-1",
        ApplicationUpdate(status=ApplicationStatus.SAVED),
    )

    assert learning.sync_application_feedback() == 1
    after = learning.get_strategy(strategy.id)
    assert after.positive_feedback == 0.5
    assert after.learned_weight > before.learned_weight
    assert learning.sync_application_feedback() == 0


def test_session_coverage_and_reflection_state_are_restart_safe(tmp_path: Path) -> None:
    database = _database(tmp_path)
    learning = JobScoutDiscoveryRepository(database)
    learning.update_session(
        "run-1",
        phase="converge",
        cycle=2,
        no_yield_cycles=1,
        increments={
            "strategies_attempted": 3,
            "results_examined": 21,
            "companies_discovered": 4,
        },
        warnings=["search provider cooling down"],
    )
    strategy = learning.ensure_strategy(
        {"kind": "public_search", "title": "Adjacent Product Role"},
        origin="deterministic_reflection",
    )
    learning.record_reflection_hypothesis(
        "run-1",
        2,
        origin="deterministic",
        hypothesis="Try an adjacent title family.",
        dimensions=strategy.dimensions,
        strategy_id=strategy.id,
    )
    learning.record_reflection_request("request-1", "run-1", 2)

    restarted = JobScoutDiscoveryRepository(database)
    session = restarted.session("run-1")
    assert session.phase == "converge"
    assert session.cycle == 2
    assert session.no_yield_cycles == 1
    assert session.coverage["strategies_attempted"] == 3
    assert session.coverage["results_examined"] == 21
    assert session.coverage["reflection_hypotheses"] == 1
    assert session.coverage["provider_warnings"] == ["search provider cooling down"]
    assert restarted.reflection_hypotheses("run-1")[0]["strategy_id"] == strategy.id
    assert restarted.reflection_request("request-1") == {
        "request_id": "request-1",
        "run_id": "run-1",
        "cycle": 2,
        "status": "queued",
    }
    restarted.mark_reflection_applied("request-1")
    assert restarted.reflection_request("request-1")["status"] == "applied"
