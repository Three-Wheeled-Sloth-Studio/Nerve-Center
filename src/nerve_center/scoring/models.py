"""Versioned location, fit, rule, and opportunity scoring contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LocationScope(StrEnum):
    LOCAL = "local"
    REGIONAL = "regional"
    DISTANT = "distant"
    UNKNOWN = "unknown"


class FactorKind(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MISSING = "missing"
    UNCERTAIN = "uncertain"
    GATE = "gate"
    NEUTRAL = "neutral"


class ScoreDimension(StrEnum):
    FIT = "fit"
    RESPONSE = "response_likelihood"
    VALUE = "opportunity_value"
    CONFIDENCE = "confidence"
    PRIORITY = "priority"


class RuleTarget(StrEnum):
    COMPANY = "company"
    DOMAIN = "domain"
    TITLE = "title"
    INDUSTRY = "industry"
    LOCATION = "location"
    EMPLOYMENT_TYPE = "employment_type"
    SOURCE = "source"


class RuleAction(StrEnum):
    HARD_INCLUDE = "hard_include"
    HARD_EXCLUDE = "hard_exclude"
    PREFER = "prefer"
    DEPRIORITIZE = "deprioritize"
    WATCH = "watch"


class RuleMatch(StrEnum):
    EXACT = "exact"
    CONTAINS = "contains"


class QualificationImportance(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    RESPONSIBILITY = "responsibility"


class MatchLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"
    UNKNOWN = "unknown"


class GateCategory(StrEnum):
    NONE = "none"
    LICENSE = "license"
    CLEARANCE = "clearance"


class GeoPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class LocationPreferences(BaseModel):
    id: str = "canonical"
    version: int = 0
    home_label: str | None = None
    home_point: GeoPoint | None = None
    home_region: str | None = None
    regional_regions: list[str] = Field(default_factory=list)
    local_max_commute_minutes: int = Field(default=90, ge=1, le=300)
    road_distance_factor: float = Field(default=1.25, ge=1, le=3)
    assumed_drive_mph: float = Field(default=45, ge=5, le=100)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OfficeLocation(BaseModel):
    id: str
    label: str
    address_text: str | None = None
    point: GeoPoint | None = None
    region: str | None = None
    country: str | None = None
    relevant_to_function: bool = True
    evidence_url: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class CompanyEnrichment(BaseModel):
    company_id: str
    offices: list[OfficeLocation] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    distributed_hiring_score: float | None = Field(default=None, ge=0, le=1)
    distributed_hiring_evidence: list[str] = Field(default_factory=list)
    hiring_activity_score: float | None = Field(default=None, ge=0, le=100)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobEnrichment(BaseModel):
    job_id: str
    point: GeoPoint | None = None
    region: str | None = None
    country: str | None = None
    commute_minutes: float | None = Field(default=None, ge=0, le=1440)
    relocation_required: bool | None = None
    remote_scope: str | None = None
    compensation_min: float | None = Field(default=None, ge=0)
    compensation_max: float | None = Field(default=None, ge=0)
    compensation_currency: str | None = None
    compensation_period: str | None = None
    repost_signal: bool | None = None
    evergreen_signal: bool | None = None
    conflicting_source_data: bool = False
    application_friction_score: float | None = Field(default=None, ge=0, le=100)
    location_confidence: float = Field(default=0.5, ge=0, le=1)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QualificationAssessment(BaseModel):
    id: str
    importance: QualificationImportance
    requirement: str
    job_excerpt: str
    matched_claim_ids: list[str] = Field(default_factory=list)
    match_level: MatchLevel
    confidence: float = Field(ge=0, le=1)
    gate_category: GateCategory = GateCategory.NONE
    notes: str | None = None


class JobFitAnalysis(BaseModel):
    id: str
    job_id: str
    profile_version: int
    contract_version: str
    model: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    qualifications: list[QualificationAssessment] = Field(default_factory=list)
    seniority_score: float = Field(default=50, ge=0, le=100)
    domain_score: float = Field(default=50, ge=0, le=100)
    leadership_score: float = Field(default=50, ge=0, le=100)
    methods_score: float = Field(default=50, ge=0, le=100)
    outcomes_score: float = Field(default=50, ge=0, le=100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    review_notes: list[str] = Field(default_factory=list)


class ExtractedQualificationAssessment(BaseModel):
    importance: QualificationImportance
    requirement: str = Field(min_length=1, max_length=1000)
    job_excerpt: str = Field(min_length=1, max_length=2000)
    matched_claim_ids: list[str] = Field(default_factory=list)
    match_level: MatchLevel
    confidence: float = Field(ge=0, le=1)
    gate_category: GateCategory = GateCategory.NONE
    notes: str | None = Field(default=None, max_length=1000)


class FitAnalysisResponse(BaseModel):
    qualifications: list[ExtractedQualificationAssessment]
    seniority_score: float = Field(ge=0, le=100)
    domain_score: float = Field(ge=0, le=100)
    leadership_score: float = Field(ge=0, le=100)
    methods_score: float = Field(ge=0, le=100)
    outcomes_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)


class ScoringWeights(BaseModel):
    fit: float = Field(default=0.35, ge=0)
    response_likelihood: float = Field(default=0.45, ge=0)
    opportunity_value: float = Field(default=0.20, ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        if self.fit + self.response_likelihood + self.opportunity_value <= 0:
            raise ValueError("at least one priority weight must be positive")
        return self


class ConfidenceBand(BaseModel):
    minimum: float = Field(ge=0, le=100)
    multiplier: float = Field(ge=0, le=1)


class ScoringSettings(BaseModel):
    id: str = "canonical"
    version: int = 1
    contract_version: str = "job-scout-score-v1"
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    confidence_bands: list[ConfidenceBand] = Field(
        default_factory=lambda: [
            ConfidenceBand(minimum=90, multiplier=1.0),
            ConfidenceBand(minimum=75, multiplier=0.95),
            ConfidenceBand(minimum=60, multiplier=0.85),
            ConfidenceBand(minimum=40, multiplier=0.70),
            ConfidenceBand(minimum=0, multiplier=0.55),
        ]
    )
    minimum_fit: float = Field(default=0, ge=0, le=100)
    minimum_response_likelihood: float = Field(default=0, ge=0, le=100)
    minimum_opportunity_value: float = Field(default=0, ge=0, le=100)
    minimum_compensation: float | None = Field(default=None, ge=0)
    desired_compensation: float | None = Field(default=None, ge=0)
    preferred_employment_types: list[str] = Field(default_factory=list)
    excluded_employment_types: list[str] = Field(default_factory=list)
    distant_remote_penalty: float = Field(default=25, ge=0, le=100)
    exceptional_fit_threshold: float = Field(default=95, ge=0, le=100)
    exceptional_required_coverage: float = Field(default=0.95, ge=0, le=1)
    prefer_rule_adjustment: float = Field(default=10, ge=0, le=100)
    deprioritize_rule_adjustment: float = Field(default=-10, ge=-100, le=0)
    hard_include_priority_floor: float = Field(default=60, ge=0, le=100)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScoringRule(BaseModel):
    id: str
    target: RuleTarget
    action: RuleAction
    pattern: str = Field(min_length=1, max_length=500)
    match: RuleMatch = RuleMatch.CONTAINS
    adjustment: float | None = Field(default=None, ge=-100, le=100)
    enabled: bool = True
    note: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScoreFactor(BaseModel):
    dimension: ScoreDimension
    code: str
    label: str
    kind: FactorKind
    points: float = 0
    confidence: float = Field(default=1, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    detail: dict[str, Any] = Field(default_factory=dict)


class HardGate(BaseModel):
    code: str
    label: str
    excludes: bool = True
    evidence: list[str] = Field(default_factory=list)


class LocationAssessment(BaseModel):
    scope: LocationScope
    commute_minutes: float | None = None
    nearest_office_id: str | None = None
    nearest_office_minutes: float | None = None
    location_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    rationale: list[str] = Field(default_factory=list)


class OpportunityScore(BaseModel):
    id: str
    job_id: str
    profile_version: int
    contract_version: str
    settings_version: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    fit: float = Field(ge=0, le=100)
    response_likelihood: float = Field(ge=0, le=100)
    opportunity_value: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    confidence_multiplier: float = Field(ge=0, le=1)
    base_priority: float = Field(ge=0, le=100)
    priority: float = Field(ge=0, le=100)
    excluded: bool = False
    retained: bool = True
    gates: list[HardGate] = Field(default_factory=list)
    factors: list[ScoreFactor] = Field(default_factory=list)
    location: LocationAssessment
    calculation: dict[str, Any] = Field(default_factory=dict)
    job_snapshot_hash: str
    profile_snapshot_hash: str
    calibration_key: str
