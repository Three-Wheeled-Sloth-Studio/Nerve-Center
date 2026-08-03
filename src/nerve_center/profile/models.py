"""Canonical career evidence and extraction contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class DocumentFormat(StrEnum):
    TEXT = "text"
    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"


class DocumentSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    locator: str
    text: str


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source_path: str
    file_name: str
    format: DocumentFormat
    media_type: str
    sha256: str
    byte_size: int
    modified_at: datetime
    imported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    segments: list[DocumentSegment]

    @property
    def analysis_text(self) -> str:
        return "\n".join(f"[{item.locator}] {item.text}" for item in self.segments)


class ClaimCategory(StrEnum):
    ROLE = "role"
    CAPABILITY = "capability"
    INDUSTRY = "industry"
    METHOD = "method"
    TECHNOLOGY = "technology"
    LEADERSHIP_SCOPE = "leadership_scope"
    OUTCOME = "outcome"
    CONSTRAINT = "constraint"
    EDUCATION = "education"


class ClaimDecision(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class EvidenceOrigin(StrEnum):
    DOCUMENT = "document"
    USER_CONFIRMED = "user_confirmed"


class EvidenceReference(BaseModel):
    origin: EvidenceOrigin
    document_id: str | None = None
    locator: str
    excerpt: str


class CareerClaim(BaseModel):
    id: str
    category: ClaimCategory
    label: str
    statement: str
    confidence: float = Field(ge=0, le=1)
    decision: ClaimDecision = ClaimDecision.PROPOSED
    evidence: list[EvidenceReference] = Field(min_length=1)


class HypothesisDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DISAPPROVED = "disapproved"


class PositioningHypothesis(BaseModel):
    id: str
    label: str
    summary: str
    suggested_headline: str
    supporting_claim_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    decision: HypothesisDecision = HypothesisDecision.PENDING


ReviewCode: TypeAlias = Literal[
    "invalid_evidence",
    "low_confidence",
    "possible_contradiction",
]


class ProfileReviewItem(BaseModel):
    id: str
    code: ReviewCode
    message: str
    claim_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CanonicalCareerProfile(BaseModel):
    id: str = "canonical"
    version: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    claims: list[CareerClaim] = Field(default_factory=list)
    hypotheses: list[PositioningHypothesis] = Field(default_factory=list)
    review_items: list[ProfileReviewItem] = Field(default_factory=list)


class ExtractedEvidence(BaseModel):
    locator: str
    excerpt: str


class ExtractedClaim(BaseModel):
    category: ClaimCategory
    label: str = Field(min_length=1, max_length=160)
    statement: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    evidence: list[ExtractedEvidence] = Field(min_length=1)


class ExtractedPositioningHypothesis(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1000)
    suggested_headline: str = Field(min_length=1, max_length=200)
    supporting_claim_labels: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class CareerExtractionResponse(BaseModel):
    claims: list[ExtractedClaim]
    positioning_hypotheses: list[ExtractedPositioningHypothesis]
