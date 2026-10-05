from datetime import UTC, datetime, timedelta

from nerve_center.config import Settings
from nerve_center.discovery.models import (
    AcquisitionClass,
    DiscoverySource,
    JobProvenance,
    NormalizedJobOpening,
    ScanStatus,
    SourceKind,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import DiscoverySourceRepository
from nerve_center.plugins.job_scout.verification import (
    VerificationStatus,
    assess_opening_verification,
)


def _repository(tmp_path):
    database = Database(Settings(data_dir=tmp_path / "runtime"))
    database.initialize()
    return DiscoverySourceRepository(database)


def _opening(*, direct: bool = False) -> NormalizedJobOpening:
    discovered = datetime.now(UTC) - timedelta(minutes=5)
    return NormalizedJobOpening(
        id="job-1",
        company_id="company-1",
        company_name="Example",
        company_domain="example.com",
        title="Director of Product",
        description="Lead product strategy.",
        source_url="https://board.example/jobs/1",
        canonical_url="https://board.example/jobs/1",
        discovered_at=discovered,
        provenance=[
            JobProvenance(
                source_id="source-direct" if direct else "source-board",
                connector="fixture",
                parser_version="v1",
                source_url=(
                    "https://example.com/jobs/1"
                    if direct
                    else "https://board.example/jobs/1"
                ),
                direct_employer_source=direct,
                discovered_at=discovered,
            )
        ],
    )


def _source(repository, *, kind=SourceKind.GREENHOUSE) -> DiscoverySource:
    source = DiscoverySource(
        id="source-employer",
        company_id="company-1",
        name="Example careers",
        kind=kind,
        acquisition_class=AcquisitionClass.PUBLIC_STRUCTURED_FEED,
        base_url="https://boards.greenhouse.io/example",
        parser_version="fixture-v1",
    )
    return repository.upsert(source)


def _scan(
    repository,
    status: ScanStatus,
    *,
    openings_found: int = 0,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> None:
    finished = finished_at or datetime.now(UTC)
    started = started_at or finished - timedelta(seconds=1)
    repository.record_scan(
        "source-employer",
        started_at=started,
        finished_at=finished,
        status=status,
        requests_made=1,
        openings_found=openings_found,
    )


def test_direct_employer_provenance_is_verified_present(tmp_path) -> None:
    repository = _repository(tmp_path)

    result = assess_opening_verification(_opening(direct=True), repository)

    assert result.status is VerificationStatus.VERIFIED_PRESENT
    assert result.actionable is True


def test_missing_authoritative_source_is_unverified_but_actionable(tmp_path) -> None:
    repository = _repository(tmp_path)

    result = assess_opening_verification(_opening(), repository)

    assert result.status is VerificationStatus.UNVERIFIED_SOURCE_UNRESOLVED
    assert result.actionable is True


def test_failed_authoritative_scan_does_not_become_verified_absent(tmp_path) -> None:
    repository = _repository(tmp_path)
    _source(repository)
    _scan(repository, ScanStatus.ACCESS_FAILED)

    result = assess_opening_verification(_opening(), repository)

    assert result.status is VerificationStatus.UNVERIFIED_SOURCE_UNAVAILABLE
    assert result.actionable is True


def test_parser_failure_is_distinct_from_listing_absence(tmp_path) -> None:
    repository = _repository(tmp_path)
    _source(repository)
    _scan(repository, ScanStatus.PARSER_FAILED)

    result = assess_opening_verification(_opening(), repository)

    assert result.status is VerificationStatus.UNVERIFIED_PARSE_FAILED
    assert result.actionable is True


def test_successful_empty_authoritative_inventory_can_verify_absence(tmp_path) -> None:
    repository = _repository(tmp_path)
    _source(repository, kind=SourceKind.GREENHOUSE)
    _scan(repository, ScanStatus.SUCCEEDED, openings_found=0)

    result = assess_opening_verification(_opening(), repository)

    assert result.status is VerificationStatus.VERIFIED_ABSENT
    assert result.actionable is False


def test_successful_nonempty_inventory_without_match_stays_unverified(tmp_path) -> None:
    repository = _repository(tmp_path)
    _source(repository, kind=SourceKind.GREENHOUSE)
    _scan(repository, ScanStatus.SUCCEEDED, openings_found=8)

    result = assess_opening_verification(_opening(), repository)

    assert result.status is VerificationStatus.UNVERIFIED_SOURCE_UNRESOLVED
    assert result.actionable is True


def test_non_exhaustive_empty_page_does_not_verify_absence(tmp_path) -> None:
    repository = _repository(tmp_path)
    _source(repository, kind=SourceKind.JSON_LD)
    _scan(repository, ScanStatus.SUCCEEDED, openings_found=0)

    result = assess_opening_verification(_opening(), repository)

    assert result.status is VerificationStatus.UNVERIFIED_SOURCE_UNRESOLVED
    assert result.actionable is True


def test_direct_observation_during_latest_scan_remains_verified(tmp_path) -> None:
    repository = _repository(tmp_path)
    _source(repository)
    scan_start = datetime.now(UTC) - timedelta(seconds=2)
    observed = scan_start + timedelta(seconds=1)
    opening = _opening(direct=True).model_copy(
        update={
            "discovered_at": observed,
            "provenance": [
                _opening(direct=True).provenance[0].model_copy(
                    update={
                        "source_id": "source-employer",
                        "discovered_at": observed,
                    }
                )
            ],
        }
    )
    _scan(
        repository,
        ScanStatus.SUCCEEDED,
        openings_found=4,
        started_at=scan_start,
        finished_at=scan_start + timedelta(seconds=2),
    )

    result = assess_opening_verification(opening, repository)

    assert result.status is VerificationStatus.VERIFIED_PRESENT
    assert result.actionable is True


def test_later_successful_exhaustive_scan_can_verify_prior_direct_opening_absent(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    _source(repository)
    opening = _opening(direct=True).model_copy(
        update={
            "provenance": [
                _opening(direct=True).provenance[0].model_copy(
                    update={"source_id": "source-employer"}
                )
            ]
        }
    )
    scan_start = datetime.now(UTC)
    _scan(
        repository,
        ScanStatus.SUCCEEDED,
        openings_found=7,
        started_at=scan_start,
        finished_at=scan_start + timedelta(seconds=1),
    )

    result = assess_opening_verification(opening, repository)

    assert result.status is VerificationStatus.VERIFIED_ABSENT
    assert result.actionable is False
    assert result.reason == (
        "later_successful_authoritative_inventory_no_longer_observes_opening"
    )


def test_later_failed_refresh_makes_prior_direct_verification_stale(tmp_path) -> None:
    repository = _repository(tmp_path)
    _source(repository)
    opening = _opening(direct=True).model_copy(
        update={
            "provenance": [
                _opening(direct=True).provenance[0].model_copy(
                    update={"source_id": "source-employer"}
                )
            ]
        }
    )
    scan_start = datetime.now(UTC)
    _scan(
        repository,
        ScanStatus.ACCESS_FAILED,
        started_at=scan_start,
        finished_at=scan_start + timedelta(seconds=1),
    )

    result = assess_opening_verification(opening, repository)

    assert result.status is VerificationStatus.STALE_VERIFICATION
    assert result.actionable is True
