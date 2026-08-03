"""Durable application tracking and review contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from nerve_center.discovery.models import Company, NormalizedJobOpening
from nerve_center.scoring.models import OpportunityScore


class ApplicationStatus(StrEnum):
    DISCOVERED = "discovered"
    SAVED = "saved"
    DISMISSED = "dismissed"
    PLANNED_TO_APPLY = "planned_to_apply"
    APPLYING = "applying"
    APPLIED = "applied"
    RECRUITER_CONTACT = "recruiter_contact"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CLOSED_WITHOUT_RESPONSE = "closed_without_response"


class ReferralStatus(StrEnum):
    NONE = "none"
    REQUESTED = "requested"
    REFERRED = "referred"
    DECLINED = "declined"
    UNKNOWN = "unknown"


class ApplicationRecord(BaseModel):
    job_id: str
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    application_date: date | None = None
    source: str | None = Field(default=None, max_length=500)
    resume_variant_reference: str | None = Field(default=None, max_length=1000)
    referral_status: ReferralStatus = ReferralStatus.NONE
    response_date: date | None = None
    disposition_reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=10000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    application_date: date | None = None
    source: str | None = Field(default=None, max_length=500)
    resume_variant_reference: str | None = Field(default=None, max_length=1000)
    referral_status: ReferralStatus | None = None
    response_date: date | None = None
    disposition_reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=10000)


class ApplicationEvent(BaseModel):
    id: str
    job_id: str
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detail: dict[str, Any] = Field(default_factory=dict)


class ReviewOpportunity(BaseModel):
    opening: NormalizedJobOpening
    company: Company
    score: OpportunityScore | None = None
    application: ApplicationRecord
    next_action: str


RESPONSE_STATUSES = {
    ApplicationStatus.RECRUITER_CONTACT,
    ApplicationStatus.SCREENING,
    ApplicationStatus.INTERVIEWING,
    ApplicationStatus.OFFER,
    ApplicationStatus.REJECTED,
}
