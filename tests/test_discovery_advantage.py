from datetime import UTC, datetime, timedelta

from nerve_center.discovery.models import JobProvenance
from nerve_center.scoring.discovery_advantage import (
    DiscoveryAdvantageClass,
    assess_discovery_advantage,
)


def _provenance(
    source_id: str,
    when: datetime,
    *,
    direct: bool,
) -> JobProvenance:
    return JobProvenance(
        source_id=source_id,
        connector="fixture",
        parser_version="v1",
        source_url=f"https://example.test/{source_id}",
        direct_employer_source=direct,
        discovered_at=when,
    )


def test_direct_only_has_strongest_observed_advantage() -> None:
    now = datetime.now(UTC)
    result = assess_discovery_advantage([_provenance("direct", now, direct=True)])

    assert result.classification is DiscoveryAdvantageClass.DIRECT_ONLY
    assert result.response_adjustment == 6.0
    assert result.secondary_source_count == 0
    assert result.detail["observation_scope"] == "retained_provenance_only"


def test_direct_first_then_secondary_keeps_smaller_advantage() -> None:
    now = datetime.now(UTC)
    result = assess_discovery_advantage(
        [
            _provenance("direct", now, direct=True),
            _provenance("board", now + timedelta(days=2), direct=False),
        ]
    )

    assert (
        result.classification
        is DiscoveryAdvantageClass.DIRECT_FIRST_LATER_SYNDICATED
    )
    assert result.response_adjustment == 3.0
    assert result.direct_first_seen_at == now
    assert result.secondary_first_seen_at == now + timedelta(days=2)


def test_secondary_first_then_direct_verification_is_neutral() -> None:
    now = datetime.now(UTC)
    result = assess_discovery_advantage(
        [
            _provenance("board", now, direct=False),
            _provenance("direct", now + timedelta(hours=4), direct=True),
        ]
    )

    assert (
        result.classification
        is DiscoveryAdvantageClass.SECONDARY_FIRST_LATER_VERIFIED
    )
    assert result.response_adjustment == 0.0


def test_multiple_secondary_sources_signal_broad_syndication() -> None:
    now = datetime.now(UTC)
    result = assess_discovery_advantage(
        [
            _provenance("direct", now, direct=True),
            _provenance("board-a", now + timedelta(hours=1), direct=False),
            _provenance("board-b", now + timedelta(hours=2), direct=False),
            _provenance("board-c", now + timedelta(hours=3), direct=False),
        ]
    )

    assert result.classification is DiscoveryAdvantageClass.BROADLY_SYNDICATED
    assert result.response_adjustment == -3.0
    assert result.secondary_source_count == 3


def test_secondary_only_is_not_misrepresented_as_board_absence() -> None:
    now = datetime.now(UTC)
    result = assess_discovery_advantage([_provenance("secondary", now, direct=False)])

    assert result.classification is DiscoveryAdvantageClass.SECONDARY_ONLY
    assert result.response_adjustment == -1.0
    assert result.detail["observation_scope"] == "retained_provenance_only"
