from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    ScanStatus,
    SourceKind,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.persistence.scoring import (
    CompanyEnrichmentRepository,
    OpportunityScoreRepository,
)
from nerve_center.plugins.job_scout.findings import register_job_scout_findings_routes
from nerve_center.plugins.job_scout.settings import (
    JobScoutConfiguration,
    JobScoutConfigurationStore,
)
from nerve_center.scoring.engine import SCORING_ENGINE_VERSION
from nerve_center.scoring.models import (
    CompanyEnrichment,
    LocationAssessment,
    LocationScope,
    OfficeLocation,
    OpportunityScore,
)


def _database(tmp_path: Path) -> tuple[Database, Settings]:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    return database, settings


def _score(job_id: str, *, priority: float, fit: float, resume_label: str) -> OpportunityScore:
    return OpportunityScore(
        id=f"score-{job_id}-{resume_label}",
        job_id=job_id,
        profile_version=1,
        contract_version="job-scout-score-v1",
        settings_version=1,
        resume_document_id=f"resume-{resume_label}",
        resume_label=resume_label,
        fit=fit,
        response_likelihood=80,
        opportunity_value=75,
        confidence=85,
        confidence_multiplier=0.95,
        base_priority=priority,
        priority=priority,
        location=LocationAssessment(
            scope=LocationScope.LOCAL,
            location_score=90,
            confidence=0.9,
        ),
        calculation={
            "scoring_engine_version": SCORING_ENGINE_VERSION,
            "fit_contract_version": "job-fit-analysis-v7",
        },
        job_snapshot_hash=f"job-{job_id}",
        profile_snapshot_hash=f"profile-{resume_label}",
        calibration_key=job_id,
    )


def test_employer_findings_surface_local_presence_and_role_metrics(tmp_path: Path) -> None:
    database, settings = _database(tmp_path)
    now = datetime.now(UTC)
    company = Company(
        id="company-local",
        canonical_name="Local Product Co",
        domain="local.example",
        career_url="https://local.example/careers",
    )
    source = DiscoverySource(
        id="source-local",
        company_id=company.id,
        name="Local Product Co careers",
        kind=SourceKind.GREENHOUSE,
        acquisition_class=AcquisitionClass.OFFICIAL_API,
        base_url="https://boards.greenhouse.io/local-product",
        parser_version="fixture-v1",
    )
    direct = NormalizedJobOpening(
        id="job-direct",
        company_id=company.id,
        company_name=company.canonical_name,
        company_domain=company.domain,
        title="Director of Product Management",
        description="Lead product strategy.",
        location_text="Remote",
        source_url="https://boards.greenhouse.io/local-product/jobs/1",
        canonical_url="https://boards.greenhouse.io/local-product/jobs/1",
        discovered_at=now - timedelta(days=5),
        provenance=[
            JobProvenance(
                source_id=source.id,
                connector="greenhouse",
                parser_version="fixture-v1",
                source_url="https://boards.greenhouse.io/local-product/jobs/1",
                direct_employer_source=True,
                discovered_at=now - timedelta(days=5),
            )
        ],
    )
    board = NormalizedJobOpening(
        id="job-board",
        company_id=company.id,
        company_name=company.canonical_name,
        company_domain=company.domain,
        title="Senior Product Manager",
        description="Own product strategy.",
        location_text="Remote",
        source_url="https://board.example/jobs/2",
        canonical_url="https://board.example/jobs/2",
        discovered_at=now - timedelta(days=20),
        provenance=[
            JobProvenance(
                source_id="source-board",
                connector="json_ld",
                parser_version="fixture-v1",
                source_url="https://board.example/jobs/2",
                direct_employer_source=False,
                discovered_at=now - timedelta(days=20),
            )
        ],
    )
    CompanyRepository(database).upsert(company)
    sources = DiscoverySourceRepository(database)
    sources.upsert(source)
    jobs = JobOpeningRepository(database)
    jobs.upsert(direct)
    jobs.upsert(board)
    CompanyEnrichmentRepository(database).save(
        CompanyEnrichment(
            company_id=company.id,
            offices=[
                OfficeLocation(
                    id="office-gso",
                    label="Greensboro, NC",
                    region="NC",
                    evidence_url="https://local.example/locations/greensboro",
                    confidence=0.9,
                )
            ],
        )
    )
    OpportunityScoreRepository(database).append(
        _score(direct.id, priority=91, fit=93, resume_label="Director")
    )
    OpportunityScoreRepository(database).append(
        _score(board.id, priority=82, fit=88, resume_label="Senior PM")
    )
    sources.record_scan(
        source.id,
        started_at=now - timedelta(minutes=1),
        finished_at=now,
        status=ScanStatus.SUCCEEDED,
        requests_made=1,
        openings_found=1,
    )
    store = JobScoutConfigurationStore(settings)
    store.save(
        JobScoutConfiguration(
            locations=["Greensboro, NC"],
            public_job_boards=[],
        )
    )
    app = FastAPI()
    register_job_scout_findings_routes(app, database, store)

    with TestClient(app) as client:
        response = client.get("/api/v1/modules/job_scout/findings/employers")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["company"]["canonical_name"] == "Local Product Co"
    assert item["presence_scope"] == "local"
    assert item["presence_evidence"] == [
        "https://local.example/locations/greensboro"
    ]
    assert item["career_source_health"] == "healthy"
    assert item["current_actionable_roles"] == 2
    assert item["current_relevant_roles"] == 2
    assert item["relevant_roles_30d"] == 2
    assert item["relevant_roles_90d"] == 2
    assert item["direct_first_roles"] == 1
    assert item["unverified_leads"] == 1
    assert item["best_role"]["title"] == "Director of Product Management"
    assert item["best_role"]["resume_label"] == "Director"


def test_employer_findings_do_not_invent_local_presence(tmp_path: Path) -> None:
    database, settings = _database(tmp_path)
    company = Company(
        id="company-unknown",
        canonical_name="Unknown Presence Co",
        domain="unknown.example",
    )
    CompanyRepository(database).upsert(company)
    store = JobScoutConfigurationStore(settings)
    store.save(
        JobScoutConfiguration(
            locations=["Greensboro, NC"],
            public_job_boards=[],
        )
    )
    app = FastAPI()
    register_job_scout_findings_routes(app, database, store)

    with TestClient(app) as client:
        response = client.get("/api/v1/modules/job_scout/findings/employers")

    item = response.json()[0]
    assert item["presence_scope"] == "unknown"
    assert item["presence_evidence"] == []
    assert item["career_source_health"] == "unresolved"
    assert item["current_actionable_roles"] == 0
