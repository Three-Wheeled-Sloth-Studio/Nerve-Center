from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nerve_center.applications.api import (
    _matches_review_geography,
    register_application_routes,
)
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


def test_review_geography_keeps_remote_and_filters_known_out_of_area_roles(
    tmp_path: Path,
) -> None:
    opening = _seed(_database(tmp_path))
    locations = ["Greensboro, NC", "Raleigh, NC", "Triad, NC"]

    assert _matches_review_geography(
        opening.model_copy(update={"work_arrangement": WorkArrangement.ON_SITE}),
        locations,
    )
    assert not _matches_review_geography(
        opening.model_copy(
            update={
                "location_text": "McLean, VA; Richmond, VA; USA",
                "work_arrangement": WorkArrangement.UNKNOWN,
            }
        ),
        locations,
    )
    assert not _matches_review_geography(
        opening.model_copy(
            update={
                "location_text": "Minneapolis, MN",
                "work_arrangement": WorkArrangement.HYBRID,
            }
        ),
        locations,
    )
    assert _matches_review_geography(
        opening.model_copy(
            update={
                "location_text": "United States",
                "work_arrangement": WorkArrangement.REMOTE,
            }
        ),
        locations,
    )
