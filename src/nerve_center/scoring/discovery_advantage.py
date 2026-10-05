"""Deterministic discovery-advantage classification from retained provenance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from nerve_center.discovery.models import JobProvenance


class DiscoveryAdvantageClass(StrEnum):
    DIRECT_ONLY = "direct_only"
    DIRECT_FIRST_LATER_SYNDICATED = "direct_first_later_syndicated"
    SECONDARY_FIRST_LATER_VERIFIED = "secondary_first_later_verified"
    BROADLY_SYNDICATED = "broadly_syndicated"
    SECONDARY_ONLY = "secondary_only"
    MIXED_SAME_TIME = "mixed_same_time"


@dataclass(frozen=True)
class DiscoveryAdvantage:
    classification: DiscoveryAdvantageClass
    response_adjustment: float
    direct_first_seen_at: datetime | None
    secondary_first_seen_at: datetime | None
    secondary_source_count: int
    provenance_count: int
    evidence_urls: tuple[str, ...]

    @property
    def detail(self) -> dict[str, object]:
        return {
            "classification": self.classification.value,
            "direct_first_seen_at": (
                self.direct_first_seen_at.isoformat()
                if self.direct_first_seen_at is not None
                else None
            ),
            "secondary_first_seen_at": (
                self.secondary_first_seen_at.isoformat()
                if self.secondary_first_seen_at is not None
                else None
            ),
            "secondary_source_count": self.secondary_source_count,
            "provenance_count": self.provenance_count,
            "observation_scope": "retained_provenance_only",
        }


def assess_discovery_advantage(
    provenance: list[JobProvenance],
) -> DiscoveryAdvantage:
    direct = [item for item in provenance if item.direct_employer_source]
    secondary = [item for item in provenance if not item.direct_employer_source]
    direct_first = min((item.discovered_at for item in direct), default=None)
    secondary_first = min((item.discovered_at for item in secondary), default=None)
    secondary_sources = {item.source_id for item in secondary}
    evidence_urls = tuple(dict.fromkeys(item.source_url for item in provenance))

    if len(secondary_sources) >= 3:
        classification = DiscoveryAdvantageClass.BROADLY_SYNDICATED
        adjustment = -3.0
    elif direct and not secondary:
        classification = DiscoveryAdvantageClass.DIRECT_ONLY
        adjustment = 6.0
    elif secondary and not direct:
        classification = DiscoveryAdvantageClass.SECONDARY_ONLY
        adjustment = -1.0
    elif direct_first is not None and secondary_first is not None:
        if direct_first < secondary_first:
            classification = DiscoveryAdvantageClass.DIRECT_FIRST_LATER_SYNDICATED
            adjustment = 3.0
        elif secondary_first < direct_first:
            classification = DiscoveryAdvantageClass.SECONDARY_FIRST_LATER_VERIFIED
            adjustment = 0.0
        else:
            classification = DiscoveryAdvantageClass.MIXED_SAME_TIME
            adjustment = 1.0
    else:
        classification = DiscoveryAdvantageClass.SECONDARY_ONLY
        adjustment = 0.0

    return DiscoveryAdvantage(
        classification=classification,
        response_adjustment=adjustment,
        direct_first_seen_at=direct_first,
        secondary_first_seen_at=secondary_first,
        secondary_source_count=len(secondary_sources),
        provenance_count=len(provenance),
        evidence_urls=evidence_urls,
    )
