"""Deterministic, provenance-preserving career evidence matching."""

from __future__ import annotations

import re
from collections.abc import Iterable

from nerve_center.discovery.models import NormalizedJobOpening
from nerve_center.profile.models import CareerClaim, ClaimCategory
from nerve_center.scoring.models import (
    DomainAssessment,
    DomainRelationship,
    EvidenceRelationship,
    RequirementEvidenceMatch,
)

_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "product_management": ("product management", "product manager", "product leadership"),
    "product_strategy": ("product strategy", "portfolio strategy", "product vision"),
    "prioritization": ("prioritization", "prioritize", "investment sequencing"),
    "roadmapping": ("roadmap", "product planning", "multi year plan"),
    "customer_discovery": ("customer discovery", "user research", "voice of customer"),
    "analytics": ("analytics", "data insights", "business intelligence", "metrics"),
    "experimentation": ("experimentation", "a b testing", "hypothesis testing"),
    "go_to_market": ("go to market", "gtm", "commercialization", "product launch"),
    "cross_functional": ("cross functional", "stakeholder alignment", "matrixed teams"),
    "people_leadership": ("people leadership", "team leadership", "managed a team", "led a team"),
    "executive_leadership": ("executive leadership", "c suite", "senior leadership"),
    "delivery": ("delivery", "execution", "ship products", "launched products"),
    "platform_product": (
        "product platform",
        "platform product",
        "platform strategy",
        "api products",
        "product ecosystem",
    ),
    "b2b": ("b2b", "business to business", "enterprise customers"),
    "saas": ("saas", "software as a service", "subscription software"),
    "operations": ("operations", "operating model", "process improvement"),
}

_DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "analytics-data": ("analytics", "business intelligence", "data platform", "data products"),
    "cybersecurity": ("cybersecurity", "information security", "security software"),
    "developer-tools": ("developer tools", "developer platform", "devops", "api platform"),
    "ecommerce-retail": ("ecommerce", "e-commerce", "retail", "marketplace"),
    "financial-services": ("fintech", "financial services", "banking", "payments", "lending"),
    "government": ("government", "public sector", "civic", "federal agency"),
    "healthcare": ("healthcare", "health care", "clinical", "patient", "medical"),
    "hr-workforce": ("human resources", "workforce", "recruiting", "talent management"),
    "insurance": ("insurance", "insurtech", "underwriting", "claims management"),
    "logistics": ("logistics", "supply chain", "freight", "transportation"),
    "property": ("real estate", "property management", "housing", "mortgage", "rentals"),
    "home-services": ("home services", "lawn care", "field service", "contractors"),
}

_ADJACENT_DOMAINS = {
    frozenset(("financial-services", "insurance")),
    frozenset(("financial-services", "property")),
    frozenset(("healthcare", "insurance")),
    frozenset(("home-services", "property")),
    frozenset(("analytics-data", "developer-tools")),
    frozenset(("ecommerce-retail", "logistics")),
    frozenset(("government", "cybersecurity")),
}

_STOPWORDS = {
    "and", "are", "experience", "for", "from", "into", "knowledge", "of", "the",
    "this", "to", "using", "with", "years", "you", "your",
}
_GATE_TERMS = {"certification", "certified", "clearance", "degree", "license", "licensed"}
_GENERIC_CONCEPTS = {"cross_functional", "delivery", "operations", "people_leadership"}


class CareerEvidenceMatcher:
    """Matches requirements to persisted claims without creating new evidence."""

    def match_requirement(
        self,
        requirement: str,
        claims: Iterable[CareerClaim],
    ) -> list[RequirementEvidenceMatch]:
        requirement_tokens = _tokens(requirement)
        requirement_concepts = _concepts(requirement, _CONCEPT_ALIASES)
        gate_like = bool(requirement_tokens & _GATE_TERMS)
        matches: list[RequirementEvidenceMatch] = []
        for claim in claims:
            claim_text = f"{claim.label} {claim.statement}"
            claim_tokens = _tokens(claim_text)
            shared_tokens = requirement_tokens & claim_tokens
            lexical_coverage = len(shared_tokens) / max(1, len(requirement_tokens))
            claim_concepts = _concepts(claim_text, _CONCEPT_ALIASES)
            shared_concepts = requirement_concepts & claim_concepts

            relationship: EvidenceRelationship | None = None
            confidence = 0.0
            if len(shared_tokens) >= 2 and lexical_coverage >= 0.4:
                relationship = EvidenceRelationship.LEXICAL
                confidence = min(0.92, 0.62 + lexical_coverage * 0.3)
            elif shared_concepts and (
                len(shared_concepts) >= 2 or not shared_concepts <= _GENERIC_CONCEPTS
            ):
                relationship = EvidenceRelationship.EQUIVALENT
                confidence = min(0.85, 0.6 + len(shared_concepts) * 0.08)
            elif shared_concepts and shared_tokens:
                relationship = EvidenceRelationship.TRANSFERABLE
                confidence = 0.52

            if relationship is None:
                continue
            if gate_like and not (
                len(shared_tokens) >= 2
                and requirement_tokens & claim_tokens & _GATE_TERMS
            ):
                continue
            matches.append(
                RequirementEvidenceMatch(
                    claim_id=claim.id,
                    relationship=relationship,
                    confidence=round(confidence * claim.confidence, 3),
                    shared_concepts=sorted(shared_concepts or shared_tokens),
                    evidence_locators=sorted({item.locator for item in claim.evidence}),
                )
            )
        return sorted(matches, key=lambda item: (-item.confidence, item.claim_id))[:3]

    def assess_domain(
        self,
        opening: NormalizedJobOpening,
        claims: Iterable[CareerClaim],
        evidence_matches: Iterable[RequirementEvidenceMatch],
    ) -> DomainAssessment:
        claim_list = list(claims)
        opening_text = " ".join(
            filter(
                None,
                [opening.company_name, opening.company_domain, opening.department, opening.team,
                 opening.title, opening.description],
            )
        )
        job_domains = _concepts(opening_text, _DOMAIN_ALIASES)
        domain_claims = [item for item in claim_list if item.category is ClaimCategory.INDUSTRY]
        career_domains: set[str] = set()
        claims_by_domain: dict[str, set[str]] = {}
        for claim in domain_claims:
            for domain in _concepts(f"{claim.label} {claim.statement}", _DOMAIN_ALIASES):
                career_domains.add(domain)
                claims_by_domain.setdefault(domain, set()).add(claim.id)

        direct = job_domains & career_domains
        adjacent_pairs = [
            (job, career)
            for job in job_domains
            for career in career_domains
            if frozenset((job, career)) in _ADJACENT_DOMAINS
        ]
        if direct:
            relationship = DomainRelationship.DIRECT
            confidence = 0.9
            supporting_domains = direct
        elif adjacent_pairs:
            relationship = DomainRelationship.ADJACENT
            confidence = 0.75
            supporting_domains = {career for _job, career in adjacent_pairs}
        elif any(True for _item in evidence_matches):
            relationship = DomainRelationship.TRANSFERABLE
            confidence = 0.6 if job_domains and career_domains else 0.45
            supporting_domains = career_domains
        else:
            relationship = DomainRelationship.MISMATCH
            confidence = 0.7 if job_domains else 0.35
            supporting_domains = set()

        supporting_claims = sorted(
            {
                claim_id
                for domain in supporting_domains
                for claim_id in claims_by_domain.get(domain, set())
            }
        )
        locators = sorted(
            {
                evidence.locator
                for claim in domain_claims
                if claim.id in supporting_claims
                for evidence in claim.evidence
            }
        )
        return DomainAssessment(
            relationship=relationship,
            confidence=confidence,
            job_domains=sorted(job_domains),
            career_domains=sorted(career_domains),
            matched_claim_ids=supporting_claims,
            evidence_locators=locators,
        )


def _concepts(value: str, aliases: dict[str, tuple[str, ...]]) -> set[str]:
    normalized = " ".join(re.findall(r"[a-z0-9]+", value.casefold()))
    return {
        concept
        for concept, phrases in aliases.items()
        if any(
            " ".join(re.findall(r"[a-z0-9]+", phrase.casefold())) in normalized
            for phrase in phrases
        )
    }


def _tokens(value: str) -> set[str]:
    aliases = {
        "led": "lead",
        "leading": "lead",
        "managed": "manage",
        "products": "product",
        "teams": "team",
    }
    return {
        aliases.get(token, token)
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) > 2 and token not in _STOPWORDS
    }
