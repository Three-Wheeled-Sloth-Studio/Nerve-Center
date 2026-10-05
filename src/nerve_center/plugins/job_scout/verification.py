"""Deterministic employer-authoritative verification semantics for Job Scout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from nerve_center.discovery.models import (
    Company,
    DiscoverySource,
    JobProvenance,
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
        direct_assessment = _assess_direct_observations(direct, sources)
        if direct_assessment is not None:
            return direct_assessment

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


def _assess_direct_observations(
    direct: list[JobProvenance],
    sources: DiscoverySourceRepository,
) -> VerificationAssessment | None:
    """Reconcile prior direct observations against later authoritative scans."""

    source_ids: list[str] = []
    evidence_urls: list[str] = []
    current: list[str] = []
    absent: list[str] = []
    stale: list[str] = []

    for provenance in direct:
        source_id = provenance.source_id
        source_url = provenance.source_url
        observed_at = provenance.discovered_at
        if source_id and source_id not in source_ids:
            source_ids.append(source_id)
        if source_url and source_url not in evidence_urls:
            evidence_urls.append(source_url)
        try:
            source = sources.get(source_id)
        except KeyError:
            current.append(source_id)
            continue
        if not _is_employer_authoritative(source):
            continue
        scans = sources.list_scans(source.id, limit=1)
        if not scans or observed_at is None:
            current.append(source.id)
            continue
        latest = scans[0]
        if latest.finished_at < observed_at:
            current.append(source.id)
            continue
        if latest.started_at <= observed_at <= latest.finished_at:
            current.append(source.id)
            continue
        if latest.started_at <= observed_at:
            current.append(source.id)
            continue
        if (
            latest.status is ScanStatus.SUCCEEDED
            and source.kind in _EXHAUSTIVE_INVENTORY_KINDS
        ):
            absent.append(source.id)
        else:
            stale.append(source.id)

    if current:
        return VerificationAssessment(
            status=VerificationStatus.VERIFIED_PRESENT,
            reason="opening_observed_on_current_employer_authoritative_source",
            authoritative_source_ids=tuple(source_ids),
            evidence_urls=tuple(evidence_urls),
        )
    if absent and not stale:
        return VerificationAssessment(
            status=VerificationStatus.VERIFIED_ABSENT,
            reason="later_successful_authoritative_inventory_no_longer_observes_opening",
            authoritative_source_ids=tuple(source_ids),
            evidence_urls=tuple(evidence_urls),
        )
    if stale:
        return VerificationAssessment(
            status=VerificationStatus.STALE_VERIFICATION,
            reason="prior_authoritative_verification_followed_by_inconclusive_refresh",
            authoritative_source_ids=tuple(source_ids),
            evidence_urls=tuple(evidence_urls),
        )
    return None


def source_confidence_for_verification(
    assessment: VerificationAssessment,
) -> tuple[float, str]:
    """Map verification truth to a bounded scoring signal, not a fit signal."""

    scores = {
        VerificationStatus.VERIFIED_PRESENT: 100.0,
        VerificationStatus.STALE_VERIFICATION: 70.0,
        VerificationStatus.UNVERIFIED_SOURCE_UNRESOLVED: 60.0,
        VerificationStatus.UNVERIFIED_SOURCE_UNAVAILABLE: 55.0,
        VerificationStatus.UNVERIFIED_PARSE_FAILED: 50.0,
        VerificationStatus.VERIFIED_ABSENT: 0.0,
    }
    return scores[assessment.status], assessment.status.value


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
