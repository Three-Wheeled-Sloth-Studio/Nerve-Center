"""Canonical career profile construction and deterministic validation."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from nerve_center.profile.models import (
    CanonicalCareerProfile,
    CareerClaim,
    CareerExtractionResponse,
    ClaimCategory,
    ClaimDecision,
    EvidenceOrigin,
    EvidenceReference,
    ExtractedClaim,
    HypothesisDecision,
    PositioningHypothesis,
    ProfileReviewItem,
    ReviewCode,
    SourceDocument,
)
from nerve_center.profile.prompts import (
    CAREER_EXTRACTION_CONTRACT_VERSION,
    SYSTEM_PROMPT,
    build_extraction_prompt,
)
from nerve_center.providers.base import StructuredProvider

_WHITESPACE = re.compile(r"\s+")


class CareerProfileStore(Protocol):
    def get_profile(self) -> CanonicalCareerProfile: ...

    def save_profile(self, profile: CanonicalCareerProfile) -> CanonicalCareerProfile: ...


class CareerProfileService:
    def __init__(self, store: CareerProfileStore, provider: StructuredProvider) -> None:
        self.store = store
        self.provider = provider

    async def extract_document(
        self,
        document: SourceDocument,
        *,
        model: str,
    ) -> CanonicalCareerProfile:
        result = await self.provider.generate_structured(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_extraction_prompt(document),
            response_type=CareerExtractionResponse,
            contract_version=CAREER_EXTRACTION_CONTRACT_VERSION,
        )
        current = self.store.get_profile()
        merged = merge_extraction(current, document, result.value)
        return self.store.save_profile(merged)

    def decide_hypothesis(
        self,
        hypothesis_id: str,
        decision: HypothesisDecision,
    ) -> CanonicalCareerProfile:
        profile = self.store.get_profile()
        found = False
        hypotheses: list[PositioningHypothesis] = []
        for hypothesis in profile.hypotheses:
            if hypothesis.id == hypothesis_id:
                hypothesis = hypothesis.model_copy(update={"decision": decision})
                found = True
            hypotheses.append(hypothesis)
        if not found:
            raise KeyError(f"unknown positioning hypothesis: {hypothesis_id}")
        return self.store.save_profile(
            profile.model_copy(
                update={
                    "hypotheses": hypotheses,
                    "version": profile.version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
        )

    def override_claim(
        self,
        claim_id: str,
        *,
        label: str,
        statement: str,
        category: ClaimCategory | None = None,
    ) -> CanonicalCareerProfile:
        profile = self.store.get_profile()
        found = False
        claims: list[CareerClaim] = []
        for claim in profile.claims:
            if claim.id == claim_id:
                claim = claim.model_copy(
                    update={
                        "category": category or claim.category,
                        "label": label.strip(),
                        "statement": statement.strip(),
                        "confidence": 1.0,
                        "decision": ClaimDecision.CONFIRMED,
                        "evidence": [
                            EvidenceReference(
                                origin=EvidenceOrigin.USER_CONFIRMED,
                                locator="user_override",
                                excerpt=statement.strip(),
                            )
                        ],
                    }
                )
                found = True
            claims.append(claim)
        if not found:
            raise KeyError(f"unknown career claim: {claim_id}")
        return self.store.save_profile(
            profile.model_copy(
                update={
                    "claims": claims,
                    "version": profile.version + 1,
                    "updated_at": datetime.now(UTC),
                }
            )
        )


def merge_extraction(
    current: CanonicalCareerProfile,
    document: SourceDocument,
    extraction: CareerExtractionResponse,
) -> CanonicalCareerProfile:
    segment_map = {item.locator: item.text for item in document.segments}
    existing_by_id = {item.id: item for item in current.claims}
    claims_by_id = dict(existing_by_id)
    review_items = list(current.review_items)

    for extracted in extraction.claims:
        claim, review = _validated_claim(document.id, segment_map, extracted)
        review_items.extend(review)
        if claim is None:
            continue
        existing = existing_by_id.get(claim.id)
        if existing is not None:
            claim = _merge_claim(existing, claim)
        claims_by_id[claim.id] = claim

    review_items.extend(_contradiction_items(list(claims_by_id.values())))

    label_to_ids: dict[str, list[str]] = defaultdict(list)
    for claim in claims_by_id.values():
        label_to_ids[_normalize(claim.label)].append(claim.id)

    existing_hypotheses = {item.id: item for item in current.hypotheses}
    hypotheses_by_id = dict(existing_hypotheses)
    for extracted in extraction.positioning_hypotheses:
        supporting_ids: list[str] = []
        for label in extracted.supporting_claim_labels:
            supporting_ids.extend(label_to_ids.get(_normalize(label), []))
        supporting_ids = sorted(set(supporting_ids))
        if not supporting_ids:
            continue
        hypothesis_id = _stable_id("hypothesis", extracted.label)
        prior = existing_hypotheses.get(hypothesis_id)
        hypotheses_by_id[hypothesis_id] = PositioningHypothesis(
            id=hypothesis_id,
            label=extracted.label.strip(),
            summary=extracted.summary.strip(),
            suggested_headline=extracted.suggested_headline.strip(),
            supporting_claim_ids=supporting_ids,
            confidence=extracted.confidence,
            decision=prior.decision if prior else HypothesisDecision.PENDING,
        )

    return CanonicalCareerProfile(
        id=current.id,
        version=current.version + 1,
        updated_at=datetime.now(UTC),
        claims=sorted(claims_by_id.values(), key=lambda item: (item.category, item.label.lower())),
        hypotheses=sorted(hypotheses_by_id.values(), key=lambda item: item.label.lower()),
        review_items=_deduplicate_review_items(review_items),
    )


def _validated_claim(
    document_id: str,
    segment_map: dict[str, str],
    extracted: ExtractedClaim,
) -> tuple[CareerClaim | None, list[ProfileReviewItem]]:
    valid_evidence: list[EvidenceReference] = []
    invalid_count = 0
    for evidence in extracted.evidence:
        source_text = segment_map.get(evidence.locator)
        if source_text is None or _normalize(evidence.excerpt) not in _normalize(source_text):
            invalid_count += 1
            continue
        valid_evidence.append(
            EvidenceReference(
                origin=EvidenceOrigin.DOCUMENT,
                document_id=document_id,
                locator=evidence.locator,
                excerpt=evidence.excerpt.strip(),
            )
        )

    review: list[ProfileReviewItem] = []
    if not valid_evidence:
        review.append(
            _review_item(
                "invalid_evidence",
                f"Rejected unsupported extracted claim: {extracted.label}",
                [],
                seed=f"{document_id}:{extracted.category}:{extracted.label}",
            )
        )
        return None, review

    claim_id = _stable_id(
        "claim",
        extracted.category,
        extracted.label,
        extracted.statement,
    )
    if invalid_count:
        review.append(
            _review_item(
                "invalid_evidence",
                f"Some evidence was rejected for claim: {extracted.label}",
                [claim_id],
                seed=f"partial:{claim_id}",
            )
        )
    if extracted.confidence < 0.65:
        review.append(
            _review_item(
                "low_confidence",
                f"Review low-confidence career claim: {extracted.label}",
                [claim_id],
                seed=f"low:{claim_id}",
            )
        )

    return (
        CareerClaim(
            id=claim_id,
            category=extracted.category,
            label=extracted.label.strip(),
            statement=extracted.statement.strip(),
            confidence=extracted.confidence,
            evidence=valid_evidence,
        ),
        review,
    )


def _merge_claim(existing: CareerClaim, incoming: CareerClaim) -> CareerClaim:
    if existing.decision is ClaimDecision.CONFIRMED or any(
        item.origin is EvidenceOrigin.USER_CONFIRMED for item in existing.evidence
    ):
        return existing
    evidence_by_key = {
        (item.origin, item.document_id, item.locator, item.excerpt): item
        for item in [*existing.evidence, *incoming.evidence]
    }
    return incoming.model_copy(
        update={
            "confidence": max(existing.confidence, incoming.confidence),
            "decision": existing.decision,
            "evidence": list(evidence_by_key.values()),
        }
    )


def _contradiction_items(claims: list[CareerClaim]) -> list[ProfileReviewItem]:
    grouped: dict[tuple[ClaimCategory, str], list[CareerClaim]] = defaultdict(list)
    for claim in claims:
        if claim.decision is not ClaimDecision.REJECTED:
            grouped[(claim.category, _normalize(claim.label))].append(claim)

    result: list[ProfileReviewItem] = []
    for (category, label), group in grouped.items():
        statements = {_normalize(item.statement) for item in group}
        if len(group) > 1 and len(statements) > 1:
            claim_ids = sorted(item.id for item in group)
            result.append(
                _review_item(
                    "possible_contradiction",
                    f"Review differing {category.value} claims for {label}.",
                    claim_ids,
                    seed="contradiction:" + ":".join(claim_ids),
                )
            )
    return result


def _review_item(
    code: ReviewCode,
    message: str,
    claim_ids: list[str],
    *,
    seed: str,
) -> ProfileReviewItem:
    return ProfileReviewItem(
        id=_stable_id("review", code, seed),
        code=code,
        message=message,
        claim_ids=claim_ids,
    )


def _deduplicate_review_items(items: list[ProfileReviewItem]) -> list[ProfileReviewItem]:
    by_id = {item.id: item for item in items}
    return sorted(by_id.values(), key=lambda item: (item.code, item.message))


def _stable_id(*parts: object) -> str:
    value = "|".join(_normalize(str(part)) for part in parts)
    return str(uuid5(NAMESPACE_URL, value))


def _normalize(value: str) -> str:
    return _WHITESPACE.sub(" ", value.strip().casefold())
