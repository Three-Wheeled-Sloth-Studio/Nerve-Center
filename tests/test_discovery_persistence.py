from datetime import UTC, datetime, timedelta
from pathlib import Path

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    Company,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    ScanStatus,
    SourceHealth,
    SourceKind,
)
from nerve_center.persistence.database import Database, SCHEMA_VERSION
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
    SearchCacheRepository,
)


def _database(tmp_path: Path) -> Database:
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    return database


def _company() -> Company:
    now = datetime.now(UTC)
    return Company(
        id="company-1",
        canonical_name="Example Co",
        domain="example.com",
        created_at=now,
        updated_at=now,
    )


def _source() -> DiscoverySource:
    return DiscoverySource(
        id="source-1",
        company_id="company-1",
        name="Example Greenhouse",
        kind=SourceKind.GREENHOUSE,
        acquisition_class=AcquisitionClass.OFFICIAL_API,
        base_url="https://boards.greenhouse.io/example",
        configuration={"board_token": "example"},
        parser_version="greenhouse-v1",
        scan_interval_minutes=60,
    )


def _opening(source_id: str, *, direct: bool, description: str) -> NormalizedJobOpening:
    discovered = datetime.now(UTC)
    return NormalizedJobOpening(
        id="job-1",
        company_id="company-1",
        company_name="Example Co",
        company_domain="example.com",
        title="Product Manager",
        description=description,
        location_text="Greensboro, NC",
        source_url="https://example.com/jobs/1",
        canonical_url="https://example.com/jobs/1",
        external_id="1",
        discovered_at=discovered,
        provenance=[
            JobProvenance(
                source_id=source_id,
                connector="greenhouse" if direct else "web_search",
                parser_version="v1",
                source_url="https://example.com/jobs/1",
                external_id="1",
                direct_employer_source=direct,
                discovered_at=discovered,
            )
        ],
    )


def test_persists_registry_health_jobs_and_cache(tmp_path: Path) -> None:
    database = _database(tmp_path)
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    cache = SearchCacheRepository(database)

    companies.upsert(_company())
    sources.upsert(_source())
    indirect = jobs.upsert(_opening("source-1", direct=False, description="Aggregator copy"))
    direct = jobs.upsert(_opening("source-1", direct=True, description="Employer copy"))
    started = datetime.now(UTC)
    scan = sources.record_scan(
        "source-1",
        started_at=started,
        finished_at=started + timedelta(seconds=1),
        status=ScanStatus.THROTTLED,
        requests_made=1,
        openings_found=0,
        http_status=429,
    )
    cache.put("playwright", "product manager Greensboro", {"urls": ["https://x.test"]})

    assert indirect.id == direct.id
    assert jobs.list()[0].description == "Employer copy"
    assert len(jobs.list()[0].provenance) == 2
    assert scan.status is ScanStatus.THROTTLED
    source = sources.get("source-1")
    assert source.health is SourceHealth.DEGRADED
    assert source.rate_limit_count == 1
    assert source.next_scan_at is not None
    assert source.next_scan_at > started + timedelta(minutes=60)
    assert cache.get("playwright", "product manager Greensboro") == {"urls": ["https://x.test"]}
    assert SCHEMA_VERSION == 10


def test_search_cache_expires(tmp_path: Path) -> None:
    database = _database(tmp_path)
    cache = SearchCacheRepository(database)
    now = datetime.now(UTC)
    cache.put("browser", "query", {"urls": []}, ttl=timedelta(seconds=1), now=now)

    assert cache.get("browser", "query", now=now) == {"urls": []}
    assert cache.get("browser", "query", now=now + timedelta(seconds=2)) is None


def test_company_lookup_by_domain_preserves_resolved_identity(tmp_path: Path) -> None:
    companies = CompanyRepository(_database(tmp_path))
    companies.upsert(_company())

    found = companies.find_by_domain("example.com")

    assert found is not None
    assert found.canonical_name == "Example Co"


def test_existing_aggregator_opening_is_reassigned_to_resolved_company(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    jobs = JobOpeningRepository(database)
    companies.upsert(_company())
    companies.upsert(
        Company(
            id="company-2",
            canonical_name="Actual Employer",
            domain="actual.example",
        )
    )
    sources.upsert(_source())
    jobs.upsert(_opening("source-1", direct=False, description="Aggregator copy"))
    corrected = _opening("source-1", direct=False, description="Resolved copy").model_copy(
        update={
            "id": "job-resolved-id",
            "company_id": "company-2",
            "company_name": "Actual Employer",
            "company_domain": "actual.example",
        }
    )

    persisted = jobs.upsert(corrected)

    assert persisted.id == "job-1"
    assert persisted.company_id == "company-2"
    assert persisted.company_name == "Actual Employer"
    assert jobs.list()[0].company_domain == "actual.example"
