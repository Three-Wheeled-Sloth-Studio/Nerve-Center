"""Deterministic employer-authoritative verification semantics for Job Scout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from nerve_center.discovery.models import (
    Company,
    DiscoverySource,
    NormalizedJobOpening,
    ScanStatus,
    SourceKind,
)
from nerve_center.persistence.discovery import DiscoverySourceRepository


class VerificationStatus(StrEnum):
    VERIFIED_PRESENT = "verified_present"
    UNVERIFIED_SOURCE_UNRESOLVED = "unverified_source_unresolved"
    UNVERIFIED_SOURCE_UNAVAILABLE = "unverified_source_unavailable"
    UNVERIFIED_PARSE_FAILED = "unverified_parse_failed"
    VERIFIED_ABSENT = "verified_absent"
    STALE_VERIFICATION = "stale_verification"


@dataclass(frozen=True, slots=True)
class OpportunityLink:
    url: str | None
    kind: str
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class VerificationAssessment:
    status: VerificationStatus
    reason: str
    authoritative_source_ids: tuple[str, ...] = ()
    evidence_urls: tuple[str, ...] = ()

    @property
    def actionable(self) -> bool:
        return self.status is not VerificationStatus.VERIFIED_ABSENT


_EXHAUSTIVE_INVENTORY_KINDS = {
    SourceKind.GREENHOUSE,
    SourceKind.LEVER,
    SourceKind.ASHBY,
}


def assess_opening_verification(
    opening: NormalizedJobOpening,
    sources: DiscoverySourceRepository,
) -> VerificationAssessment:
    """Classify verification without turning access failures into negative evidence."""

    direct = [item for item in opening.provenance if item.direct_employer_source]
    if direct:
        return VerificationAssessment(
            status=VerificationStatus.VERIFIED_PRESENT,
            reason="opening_observed_on_employer_authoritative_source",
            authoritative_source_ids=tuple(dict.fromkeys(item.source_id for item in direct)),
            evidence_urls=tuple(dict.fromkeys(item.source_url for item in direct)),
        )

    employer_sources = [
        source
        for source in sources.list()
        if source.company_id == opening.company_id and _is_employer_authoritative(source)
    ]
    if not employer_sources:
        return VerificationAssessment(
            status=VerificationStatus.UNVERIFIED_SOURCE_UNRESOLVED,
            reason="no_employer_authoritative_source_resolved",
        )

    observed = []
    for source in employer_sources:
        scans = sources.list_scans(source.id, limit=1)
        if not scans:
            continue
        latest = scans[0]
        if latest.finished_at < opening.discovered_at:
            continue
        observed.append((source, latest))

    source_ids = tuple(source.id for source in employer_sources)
    urls = tuple(source.base_url for source in employer_sources)

    if not observed:
        return VerificationAssessment(
            status=VerificationStatus.UNVERIFIED_SOURCE_UNRESOLVED,
            reason="authoritative_source_not_scanned_since_lead_discovery",
            authoritative_source_ids=source_ids,
            evidence_urls=urls,
        )

    if any(scan.status is ScanStatus.PARSER_FAILED for _source, scan in observed):
        return VerificationAssessment(
            status=VerificationStatus.UNVERIFIED_PARSE_FAILED,
            reason="authoritative_source_read_but_parse_failed",
            authoritative_source_ids=source_ids,
            evidence_urls=urls,
        )

    successful = [
        (source, scan)
        for source, scan in observed
        if scan.status is ScanStatus.SUCCEEDED
    ]
    if any(
        source.kind in _EXHAUSTIVE_INVENTORY_KINDS and scan.openings_found == 0
        for source, scan in successful
    ):
        return VerificationAssessment(
            status=VerificationStatus.VERIFIED_ABSENT,
            reason="successful_authoritative_inventory_scan_returned_no_openings",
            authoritative_source_ids=source_ids,
            evidence_urls=urls,
        )

    if successful:
        return VerificationAssessment(
            status=VerificationStatus.UNVERIFIED_SOURCE_UNRESOLVED,
            reason="authoritative_source_read_without_opening_match",
            authoritative_source_ids=source_ids,
            evidence_urls=urls,
        )

    return VerificationAssessment(
        status=VerificationStatus.UNVERIFIED_SOURCE_UNAVAILABLE,
        reason="authoritative_source_scan_unavailable_or_incomplete",
        authoritative_source_ids=source_ids,
        evidence_urls=urls,
    )


def preferred_opportunity_link(
    opening: NormalizedJobOpening,
    company: Company,
    assessment: VerificationAssessment,
) -> OpportunityLink:
    """Choose the most useful user-facing link without overstating verification."""

    if assessment.status is VerificationStatus.VERIFIED_PRESENT:
        return OpportunityLink(
            url=opening.canonical_url or opening.apply_url or opening.source_url,
            kind="employer_opening",
        )
    if company.career_url:
        return OpportunityLink(
            url=company.career_url,
            kind="employer_careers",
            warning=(
                "This opening is not currently verified on an employer-authoritative source."
            ),
        )
    fallback = opening.canonical_url or opening.source_url
    return OpportunityLink(
        url=fallback,
        kind="discovery_source",
        warning=(
            "Employer-authoritative verification is unavailable; this link is a discovery source."
        ),
    )


def _is_employer_authoritative(source: DiscoverySource) -> bool:
    return bool(source.configuration.get("direct_employer_source", True)) and (
        source.configuration.get("source_role") != "aggregator_listing"
    )
