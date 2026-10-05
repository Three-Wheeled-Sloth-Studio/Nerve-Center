"""Evidence-constrained terminology alignment suggestions for Job Scout."""

from __future__ import annotations

import json
import re

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import JobOpeningRepository
from nerve_center.persistence.profile import CareerProfileRepository, SourceDocumentRepository
from nerve_center.profile.models import CareerClaim, ClaimDecision, EvidenceOrigin
from nerve_center.providers.base import StructuredProvider
from nerve_center.providers.errors import ProviderError


class TerminologyAlignmentRequest(BaseModel):
    resume_document_id: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=200)


class ProposedTerminologyPatch(BaseModel):
    original_text: str = Field(min_length=1, max_length=500)
    suggested_text: str = Field(min_length=1, max_length=500)
    listing_term: str = Field(min_length=1, max_length=200)
    supporting_claim_ids: list[str] = Field(min_length=1, max_length=8)
    reason: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class TerminologyAlignmentResponse(BaseModel):
    suggestions: list[ProposedTerminologyPatch] = Field(default_factory=list, max_length=6)


_SYSTEM_PROMPT = """Suggest only light terminology alignment edits to an existing resume.
Each suggestion must replace a short exact excerpt from the supplied resume with a close
rewording that uses terminology from the supplied job listing. Do not add a skill,
technology, credential, employer, title, date, scope, responsibility, or outcome that is
not supported by the supplied career claims. Preserve every number exactly. Keep quantified
outcomes intact. Do not rewrite whole bullets when a smaller phrase edit will work. Every
suggestion must cite one or more supplied supporting claim IDs. Return no suggestion when
the wording is not safely equivalent. The user will review suggestions; do not apply edits."""


def register_terminology_alignment_routes(
    application: FastAPI,
    database: Database,
    provider: StructuredProvider | None,
) -> None:
    documents = SourceDocumentRepository(database)
    profiles = CareerProfileRepository(database)
    jobs = JobOpeningRepository(database)

    @application.post(
        "/api/v1/modules/job_scout/jobs/{job_id}/terminology-alignment",
        response_model=TerminologyAlignmentResponse,
    )
    async def terminology_alignment(
        job_id: str,
        request: TerminologyAlignmentRequest,
    ) -> TerminologyAlignmentResponse:
        if provider is None:
            raise HTTPException(
                status_code=503,
                detail="A structured model provider is required for terminology suggestions.",
            )
        try:
            document = documents.get(request.resume_document_id)
            opening = next(
                item for item in jobs.list(active_only=False) if item.id == job_id
            )
        except (KeyError, StopIteration) as error:
            raise HTTPException(status_code=404, detail="Unknown job or resume.") from error
        claims = _resume_claims(profiles.get_profile().claims, request.resume_document_id)
        if not claims:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This resume has no extracted career evidence yet. "
                    "Analyze the resume before requesting terminology alignment."
                ),
            )
        resume_text = "\n".join(segment.text for segment in document.segments)
        prompt = "\n".join(
            [
                "Resume:",
                resume_text,
                "Verified career claims:",
                json.dumps(
                    [
                        {
                            "id": claim.id,
                            "label": claim.label,
                            "statement": claim.statement,
                        }
                        for claim in claims
                    ],
                    ensure_ascii=True,
                ),
                f"Job title: {opening.title}",
                "Job listing:",
                opening.description,
            ]
        )
        try:
            generated = await provider.generate_structured(
                model=request.model or "auto",
                system_prompt=_SYSTEM_PROMPT,
                user_prompt=prompt,
                response_type=TerminologyAlignmentResponse,
                contract_version="job-scout-terminology-alignment-v1",
            )
        except ProviderError as error:
            raise HTTPException(status_code=503, detail=error.as_dict()) from error
        valid = [
            item
            for item in generated.value.suggestions
            if _valid_patch(
                item,
                resume_text=resume_text,
                listing_text=f"{opening.title}\n{opening.description}",
                claims=claims,
            )
        ]
        return TerminologyAlignmentResponse(suggestions=valid)


def _resume_claims(
    claims: list[CareerClaim],
    resume_document_id: str,
) -> list[CareerClaim]:
    return [
        claim
        for claim in claims
        if claim.decision is not ClaimDecision.REJECTED
        and (
            any(
                evidence.document_id == resume_document_id
                for evidence in claim.evidence
            )
            or any(
                evidence.origin is EvidenceOrigin.USER_CONFIRMED
                for evidence in claim.evidence
            )
        )
    ]


def _valid_patch(
    patch: ProposedTerminologyPatch,
    *,
    resume_text: str,
    listing_text: str,
    claims: list[CareerClaim],
) -> bool:
    original = " ".join(patch.original_text.split())
    suggested = " ".join(patch.suggested_text.split())
    normalized_resume = " ".join(resume_text.split())
    normalized_listing = " ".join(listing_text.casefold().split())
    listing_term = " ".join(patch.listing_term.casefold().split())
    if (
        not original
        or not suggested
        or original == suggested
        or original not in normalized_resume
        or listing_term not in normalized_listing
    ):
        return False
    if len(suggested) > len(original) + 100:
        return False
    if re.findall(r"\d+(?:[.,]\d+)*%?", original) != re.findall(
        r"\d+(?:[.,]\d+)*%?", suggested
    ):
        return False
    claim_map = {claim.id: claim for claim in claims}
    supporting = [
        claim_map[claim_id]
        for claim_id in patch.supporting_claim_ids
        if claim_id in claim_map
    ]
    if not supporting or len(supporting) != len(set(patch.supporting_claim_ids)):
        return False
    support_text = " ".join(
        f"{claim.label} {claim.statement}" for claim in supporting
    )
    new_terms = _meaningful_tokens(suggested) - _meaningful_tokens(original)
    supported_terms = _meaningful_tokens(support_text)
    listing_terms = _meaningful_tokens(listing_text)
    return new_terms.issubset(supported_terms & listing_terms)


def _meaningful_tokens(value: str) -> set[str]:
    stop = {
        "a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on",
        "or", "the", "to", "with",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9+#.-]+", value.casefold())
        if len(token) > 1 and token not in stop
    }
