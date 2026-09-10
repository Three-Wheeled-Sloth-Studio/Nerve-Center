from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nerve_center.applications.api import register_application_routes
from nerve_center.applications.models import ApplicationStatus, ApplicationUpdate
from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    SourceKind,
    WorkArrangement,
)
from nerve_center.persistence.applications import ApplicationRepository
from nerve_center.persistence.database import SCHEMA_VERSION, Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.persistence.scoring import OpportunityScoreRepository
from nerve_center.plugins.job_scout.settings import (
    JobScoutConfiguration,
    JobScoutConfigurationStore,
)
from nerve_center.scoring.engine import SCORING_ENGINE_VERSION
from nerve_center.scoring.models import (
    LocationAssessment,
    LocationScope,
    OpportunityScore,
)


def _database(tmp_path: Path) -> Database:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    return database


def _seed(database: Database) -> NormalizedJobOpening:
    company = Company(
        id="company-1",
        canonical_name="Example Co",
        domain="example.com",
        career_url="https://example.com/careers",
    )
    source = DiscoverySource(
        id="source-1",
        company_id=company.id,
        name="Manual source",
        kind=SourceKind.MANUAL,
        acquisition_class=AcquisitionClass.MANUAL_IMPORT_ONLY,
        base_url="https://example.com/jobs",
        parser_version="manual-v1",
    )
    opening = NormalizedJobOpening(
        id="job-1",
        company_id=company.id,
        company_name=company.canonical_name,
        company_domain=company.domain,
        title="Product Manager",
        description="Lead analytics and workflow automation.",
        location_text="Greensboro, NC",
        source_url="https://example.com/jobs/1",
        canonical_url="https://example.com/jobs/1",
        discovered_at=datetime.now(UTC),
        provenance=[
            JobProvenance(
                source_id=source.id,
                connector="manual",
                parser_version="manual-v1",
                source_url="https://example.com/jobs/1",
                direct_employer_source=True,
            )
        ],
    )
    CompanyRepository(database).upsert(company)
    DiscoverySourceRepository(database).upsert(source)
    JobOpeningRepository(database).upsert(opening)
    return opening


def _opportunity_score(
    job_id: str,
    *,
    engine_version: str,
    scope: LocationScope,
    created_at: datetime,
) -> OpportunityScore:
    location_score = 100.0 if scope is LocationScope.LOCAL else 40.0
    return OpportunityScore(
        id=f"score-{engine_version}",
        job_id=job_id,
        profile_version=1,
        contract_version="job-scout-scoring-v1",
        settings_version=1,
        created_at=created_at,
        fit=80,
        response_likelihood=70,
        opportunity_value=75,
        confidence=80,
        confidence_multiplier=0.95,
        base_priority=75,
        priority=71.25,
        location=LocationAssessment(
            scope=scope,
            location_score=location_score,
            confidence=0.8,
            rationale=["fixture"],
        ),
        calculation={
            "scoring_engine_version": engine_version,
            "fit_contract_version": "job-fit-analysis-v6",
        },
        job_snapshot_hash="job-hash",
        profile_snapshot_hash="profile-hash",
        calibration_key=job_id,
    )


class _RescoreStub:
    def __init__(self, scores: OpportunityScoreRepository, job_id: str) -> None:
        self.scores = scores
        self.job_id = job_id
        self.score_calls = 0

    def score(self, job_id: str) -> OpportunityScore:
        assert job_id == self.job_id
        self.score_calls += 1
        refreshed = _opportunity_score(
            job_id,
            engine_version=SCORING_ENGINE_VERSION,
            scope=LocationScope.LOCAL,
            created_at=datetime.now(UTC),
        )
        return self.scores.append(refreshed)

    def ensure_provisional_score(self, *_args: object, **_kwargs: object) -> OpportunityScore:
        raise AssertionError("stale full-fit scores must not fall back to provisional analysis")


def test_application_status_history_and_dates(tmp_path: Path) -> None:
    database = _database(tmp_path)
    opening = _seed(database)
    repository = ApplicationRepository(database)
    now = datetime(2026, 8, 3, 18, 30, tzinfo=UTC)

    applied = repository.save(
        opening.id,
        ApplicationUpdate(status=ApplicationStatus.APPLIED),
        now=now,
    )
    repository.save(
        opening.id,
        ApplicationUpdate(status=ApplicationStatus.APPLIED),
        now=now,
    )
    screening = repository.save(
        opening.id,
        ApplicationUpdate(status=ApplicationStatus.SCREENING),
        now=now,
    )

    assert applied.application_date == now.date()
    assert screening.response_date == now.date()
    assert [event.to_status for event in repository.history(opening.id)] == [
        ApplicationStatus.SCREENING,
        ApplicationStatus.APPLIED,
    ]
    assert SCHEMA_VERSION == 11


def test_review_api_tracks_reversible_pursuit_state(tmp_path: Path) -> None:
    database = _database(tmp_path)
    opening = _seed(database)
    application = FastAPI()
    register_application_routes(application, database)

    with TestClient(application) as client:
        initial = client.get("/api/v1/review/opportunities")
        saved = client.patch(
            f"/api/v1/applications/{opening.id}",
            json={"status": "saved"},
        )
        dismissed = client.patch(
            f"/api/v1/applications/{opening.id}",
            json={"status": "dismissed"},
        )
        hidden = client.get("/api/v1/review/opportunities")
        restored = client.patch(
            f"/api/v1/applications/{opening.id}",
            json={"status": "saved"},
        )
        visible = client.get("/api/v1/review/opportunities")

    assert initial.status_code == 200
    assert initial.json()[0]["application"]["status"] == "discovered"
    assert saved.json()["status"] == "saved"
    assert dismissed.json()["status"] == "dismissed"
    assert hidden.json() == []
    assert restored.json()["status"] == "saved"
    assert visible.json()[0]["next_action"].startswith("Review details")


def test_review_backfills_stale_score_without_provisional_or_llm_path(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    opening = _seed(database)
    scores = OpportunityScoreRepository(database)
    scores.append(
        _opportunity_score(
            opening.id,
            engine_version="job-scout-ranking-v3",
            scope=LocationScope.UNKNOWN,
            created_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
    )
    configuration = JobScoutConfigurationStore(settings)
    configuration.save(
        JobScoutConfiguration(
            target_titles=["Product Manager"],
            locations=["Greensboro, NC"],
            public_job_boards=[],
        )
    )
    scoring = _RescoreStub(scores, opening.id)
    application = FastAPI()
    register_application_routes(
        application,
        database,
        scoring_service=scoring,  # type: ignore[arg-type]
        configuration_store=configuration,
    )

    with TestClient(application) as client:
        response = client.get("/api/v1/review/opportunities")

    assert response.status_code == 200
    assert scoring.score_calls == 1
    assert response.json()[0]["score"]["location"]["scope"] == "local"
    history = scores.list(opening.id)
    assert len(history) == 2
    assert history[0].calculation["scoring_engine_version"] == SCORING_ENGINE_VERSION


def test_review_keeps_distant_roles_for_explicit_scored_location_filtering(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path / "runtime")
    database = Database(settings)
    database.initialize()
    local = _seed(database)
    distant = local.model_copy(
        update={
            "id": "job-2",
            "location_text": "Minneapolis, MN",
            "work_arrangement": WorkArrangement.HYBRID,
            "source_url": "https://example.com/jobs/2",
            "canonical_url": "https://example.com/jobs/2",
            "provenance": [
                local.provenance[0].model_copy(
                    update={"source_url": "https://example.com/jobs/2"}
                )
            ],
        }
    )
    JobOpeningRepository(database).upsert(distant)
    configuration = JobScoutConfigurationStore(settings)
    configuration.save(
        JobScoutConfiguration(
            target_titles=["Product Manager"],
            locations=["Greensboro, NC"],
            public_job_boards=[],
        )
    )
    application = FastAPI()
    register_application_routes(
        application,
        database,
        configuration_store=configuration,
    )

    with TestClient(application) as client:
        response = client.get("/api/v1/review/opportunities")

    assert response.status_code == 200
    assert {item["opening"]["id"] for item in response.json()} == {"job-1", "job-2"}
