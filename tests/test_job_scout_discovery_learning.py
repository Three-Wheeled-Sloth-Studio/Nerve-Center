from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

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


def test_schema_upgrade_adds_market_relevant_yield_columns(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.settings.ensure_runtime_directories()
    with database.engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE job_scout_discovery_strategies (id VARCHAR(36) PRIMARY KEY)")
        )
        connection.execute(
            text("CREATE TABLE job_scout_strategy_attempts (id VARCHAR(36) PRIMARY KEY)")
        )

    database.initialize()

    with database.engine.begin() as connection:
        for table in (
            "job_scout_discovery_strategies",
            "job_scout_strategy_attempts",
        ):
            columns = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
            }
            assert "market_relevant_opportunities" in columns


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
            market_relevant_opportunities=2,
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
    assert saved.market_relevant_opportunities == 2
    assert saved.learned_weight == productive.learned_weight


def test_location_strategy_downweights_national_only_inventory(tmp_path: Path) -> None:
    learning = JobScoutDiscoveryRepository(_database(tmp_path))
    strategy = learning.ensure_strategy(
        {"kind": "public_search", "anchor": "Product", "location": "Greensboro, NC"},
        origin="profile",
    )

    result = learning.record_attempt(
        "run-1",
        1,
        strategy.id,
        "deepen",
        StrategyOutcome(
            results_examined=10,
            postings_inspected=100,
            opportunities_retained=40,
            market_relevant_opportunities=0,
        ),
    )

    assert result.opportunities_retained == 40
    assert result.market_relevant_opportunities == 0
    assert result.learned_weight < 1.0
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
