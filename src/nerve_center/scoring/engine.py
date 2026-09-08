"""Deterministic, reconstructable opportunity scoring engine."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from nerve_center.discovery.models import NormalizedJobOpening, WorkArrangement
from nerve_center.profile.models import CanonicalCareerProfile
from nerve_center.scoring.fit import preferred_coverage, required_coverage
from nerve_center.scoring.location import assess_location
from nerve_center.scoring.models import (
    CompanyEnrichment,
    FactorKind,
    GateCategory,
    HardGate,
    JobEnrichment,
    JobFitAnalysis,
    LocationAssessment,
    LocationPreferences,
    LocationScope,
    MatchLevel,
    OpportunityScore,
    RuleAction,
    RuleTarget,
    ScoreDimension,
    ScoreFactor,
    ScoringRule,
    ScoringSettings,
)


class OpportunityScorer:
    def score(
        self,
        *,
        opening: NormalizedJobOpening,
        profile: CanonicalCareerProfile,
        fit_analysis: JobFitAnalysis,
        company_enrichment: CompanyEnrichment,
        job_enrichment: JobEnrichment,
        location_preferences: LocationPreferences,
        settings: ScoringSettings,
        rules: list[ScoringRule],
        now: datetime | None = None,
    ) -> OpportunityScore:
        current = now or datetime.now(UTC)
        factors: list[ScoreFactor] = []
        gates: list[HardGate] = []
        location = assess_location(
            work_arrangement=opening.work_arrangement,
            job_location=job_enrichment,
            company=company_enrichment,
            preferences=location_preferences,
        )
        fit, required, preferred = _fit_score(fit_analysis, factors)
        response = _response_score(
            opening,
            company_enrichment,
            job_enrichment,
            location,
            fit,
            required,
            settings,
            current,
            factors,
        )
        value = _value_score(
            opening,
            fit_analysis,
            job_enrichment,
            location,
            settings,
            factors,
        )
        hard_include = False
        for rule in sorted((item for item in rules if item.enabled), key=lambda item: item.id):
            if not _rule_matches(rule, opening, company_enrichment):
                continue
            evidence = [f"Matched {rule.target.value}: {rule.pattern}"]
            code = f"rule:{rule.id}"
            if rule.action is RuleAction.HARD_EXCLUDE:
                gates.append(
                    HardGate(
                        code=code,
                        label=rule.note or "Matched a hard-exclude rule.",
                        evidence=evidence,
                    )
                )
            elif rule.action is RuleAction.HARD_INCLUDE:
                hard_include = True
                factors.append(
                    ScoreFactor(
                        dimension=ScoreDimension.PRIORITY,
                        code=code,
                        label=rule.note or "Matched a hard-include rule.",
                        kind=FactorKind.POSITIVE,
                        evidence=evidence,
                    )
                )
            elif rule.action in {RuleAction.PREFER, RuleAction.DEPRIORITIZE}:
                default = (
                    settings.prefer_rule_adjustment
                    if rule.action is RuleAction.PREFER
                    else settings.deprioritize_rule_adjustment
                )
                adjustment = rule.adjustment if rule.adjustment is not None else default
                value += adjustment
                factors.append(
                    ScoreFactor(
                        dimension=ScoreDimension.VALUE,
                        code=code,
                        label=rule.note or f"Matched a {rule.action.value} rule.",
                        kind=(FactorKind.POSITIVE if adjustment >= 0 else FactorKind.NEGATIVE),
                        points=adjustment,
                        evidence=evidence,
                    )
                )
            else:
                factors.append(
                    ScoreFactor(
                        dimension=ScoreDimension.PRIORITY,
                        code=code,
                        label=rule.note or "Matched a watch rule.",
                        kind=FactorKind.NEUTRAL,
                        evidence=evidence,
                    )
                )

        fit, response, value = map(_clamp, (fit, response, value))
        _apply_gates(
            opening,
            fit_analysis,
            job_enrichment,
            location,
            settings,
            fit,
            response,
            value,
            gates,
        )
        confidence = _confidence_score(
            opening,
            fit_analysis,
            job_enrichment,
            location,
            factors,
        )
        multiplier = _confidence_multiplier(confidence, settings)
        total_weight = (
            settings.weights.fit
            + settings.weights.response_likelihood
            + settings.weights.opportunity_value
        )
        weights = {
            "fit": settings.weights.fit / total_weight,
            "response_likelihood": settings.weights.response_likelihood / total_weight,
            "opportunity_value": settings.weights.opportunity_value / total_weight,
        }
        base_priority = (
            fit * weights["fit"]
            + response * weights["response_likelihood"]
            + value * weights["opportunity_value"]
        )
        calculated = _clamp(base_priority * multiplier)
        excluded = any(item.excludes for item in gates)
        retained = not excluded or hard_include
        priority = 0.0 if excluded and not hard_include else calculated
        if hard_include:
            priority = max(priority, settings.hard_include_priority_floor)

        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.CONFIDENCE,
                code="confidence_multiplier",
                label="Confidence scales final priority downward.",
                kind=FactorKind.NEUTRAL if multiplier == 1 else FactorKind.NEGATIVE,
                points=round(priority - base_priority, 2),
                confidence=confidence / 100,
                detail={"multiplier": multiplier},
            )
        )
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.PRIORITY,
                code="priority_formula",
                label="Configured component weights determine base priority.",
                kind=FactorKind.NEUTRAL,
                detail={"weights": weights},
            )
        )
        factors.extend(
            ScoreFactor(
                dimension=ScoreDimension.PRIORITY,
                code=gate.code,
                label=gate.label,
                kind=FactorKind.GATE,
                evidence=gate.evidence,
            )
            for gate in gates
        )

        return OpportunityScore(
            id=str(uuid4()),
            job_id=opening.id,
            profile_version=profile.version,
            contract_version=settings.contract_version,
            settings_version=settings.version,
            fit=round(fit, 2),
            response_likelihood=round(response, 2),
            opportunity_value=round(value, 2),
            confidence=round(confidence, 2),
            confidence_multiplier=multiplier,
            base_priority=round(base_priority, 2),
            priority=round(_clamp(priority), 2),
            excluded=excluded,
            retained=retained,
            gates=gates,
            factors=factors,
            location=location,
            calculation={
                "fit_contract_version": fit_analysis.contract_version,
                "fit_model": fit_analysis.model,
                "required_coverage": round(required, 4),
                "preferred_coverage": round(preferred, 4),
                "weights": weights,
                "calculated_priority_before_gates": round(calculated, 2),
                "hard_include": hard_include,
            },
            job_snapshot_hash=_snapshot_hash(opening.model_dump(mode="json")),
            profile_snapshot_hash=_snapshot_hash(profile.model_dump(mode="json")),
            calibration_key=opening.id,
        )


def _fit_score(
    analysis: JobFitAnalysis,
    factors: list[ScoreFactor],
) -> tuple[float, float, float]:
    required = required_coverage(analysis)
    preferred = preferred_coverage(analysis)
    components = {
        "required_coverage": required * 100,
        "preferred_coverage": preferred * 100,
        "seniority": analysis.seniority_score,
        "domain": analysis.domain_score,
        "leadership": analysis.leadership_score,
        "methods": analysis.methods_score,
        "outcomes": analysis.outcomes_score,
    }
    weights = {
        "required_coverage": 0.45,
        "preferred_coverage": 0.10,
        "seniority": 0.15,
        "domain": 0.10,
        "leadership": 0.10,
        "methods": 0.05,
        "outcomes": 0.05,
    }
    score = sum(components[key] * weights[key] for key in components)
    factors.append(
        ScoreFactor(
            dimension=ScoreDimension.FIT,
            code="fit_components",
            label="Verified requirement coverage and career alignment determine fit.",
            kind=FactorKind.NEUTRAL,
            points=score,
            confidence=analysis.confidence,
            detail={"components": components, "weights": weights},
        )
    )
    return score, required, preferred


def _response_score(
    opening: NormalizedJobOpening,
    company: CompanyEnrichment,
    job: JobEnrichment,
    location: LocationAssessment,
    fit: float,
    required: float,
    settings: ScoringSettings,
    now: datetime,
    factors: list[ScoreFactor],
) -> float:
    freshness = _freshness_score(opening, job, now, factors)
    direct = any(item.direct_employer_source for item in opening.provenance)
    provenance_score = 100.0 if direct else 60.0
    hiring_score = company.hiring_activity_score or 50.0
    if (
        opening.work_arrangement is WorkArrangement.REMOTE
        and company.distributed_hiring_score is not None
    ):
        hiring_score = (hiring_score + company.distributed_hiring_score * 100) / 2
    score = (
        location.location_score * 0.35
        + freshness * 0.15
        + provenance_score * 0.10
        + required * 100 * 0.25
        + hiring_score * 0.15
    )
    factors.append(
        ScoreFactor(
            dimension=ScoreDimension.RESPONSE,
            code="response_components",
            label="Location, freshness, provenance, required coverage, and hiring activity drive response likelihood.",
            kind=FactorKind.NEUTRAL,
            points=score,
            detail={
                "location": location.location_score,
                "freshness": freshness,
                "provenance": provenance_score,
                "required_coverage": required * 100,
                "hiring_activity": hiring_score,
            },
        )
    )
    if (
        opening.work_arrangement is WorkArrangement.REMOTE
        and location.scope is LocationScope.DISTANT
    ):
        exceptional = (
            fit >= settings.exceptional_fit_threshold
            and required >= settings.exceptional_required_coverage
        )
        penalty = 5.0 if exceptional else settings.distant_remote_penalty
        score -= penalty
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.RESPONSE,
                code="distant_remote_saturation",
                label="Distant remote roles face a substantial applicant-saturation penalty.",
                kind=FactorKind.NEGATIVE,
                points=-penalty,
                detail={"exceptional_match": exceptional},
            )
        )
    if job.conflicting_source_data:
        score -= 10
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.RESPONSE,
                code="conflicting_source_data",
                label="Conflicting source data reduces response confidence.",
                kind=FactorKind.UNCERTAIN,
                points=-10,
            )
        )
    if job.application_friction_score is not None:
        penalty = job.application_friction_score * 0.1
        score -= penalty
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.RESPONSE,
                code="application_friction",
                label="Application friction reduces likely pursuit return.",
                kind=FactorKind.NEGATIVE,
                points=-penalty,
            )
        )
    return score


def _freshness_score(
    opening: NormalizedJobOpening,
    job: JobEnrichment,
    now: datetime,
    factors: list[ScoreFactor],
) -> float:
    timestamp = opening.posted_at or opening.updated_at
    if timestamp is None:
        score = 40.0
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.RESPONSE,
                code="listing_date_missing",
                label="The listing date is missing or unreliable.",
                kind=FactorKind.MISSING,
                points=score,
            )
        )
    else:
        age = max((now - timestamp).total_seconds() / 86400, 0)
        if age <= 3:
            score = 100.0
        elif age <= 7:
            score = 90.0
        elif age <= 14:
            score = 80.0
        elif age <= 30:
            score = 65.0
        elif age <= 60:
            score = 45.0
        else:
            score = 25.0
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.RESPONSE,
                code="listing_freshness",
                label=f"The listing is approximately {age:.0f} days old.",
                kind=FactorKind.POSITIVE if age <= 14 else FactorKind.NEGATIVE,
                points=score,
                evidence=[timestamp.isoformat()],
            )
        )
    if job.repost_signal:
        score -= 10
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.RESPONSE,
                code="repost_signal",
                label="The listing appears to be reposted.",
                kind=FactorKind.NEGATIVE,
                points=-10,
            )
        )
    if job.evergreen_signal:
        score -= 20
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.RESPONSE,
                code="evergreen_signal",
                label="The listing appears evergreen rather than tied to an active opening.",
                kind=FactorKind.NEGATIVE,
                points=-20,
            )
        )
    return _clamp(score)


def _value_score(
    opening: NormalizedJobOpening,
    analysis: JobFitAnalysis,
    job: JobEnrichment,
    location: LocationAssessment,
    settings: ScoringSettings,
    factors: list[ScoreFactor],
) -> float:
    compensation = job.compensation_max or job.compensation_min
    if compensation is not None and settings.desired_compensation:
        compensation_score = _clamp(compensation / settings.desired_compensation * 100)
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.VALUE,
                code="compensation_alignment",
                label="Known compensation is compared with the configured target.",
                kind=(
                    FactorKind.POSITIVE
                    if compensation >= settings.desired_compensation
                    else FactorKind.NEGATIVE
                ),
                points=compensation_score,
                detail={"known": compensation, "desired": settings.desired_compensation},
            )
        )
    else:
        compensation_score = 50.0
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.VALUE,
                code="compensation_missing",
                label="Compensation is missing or no target is configured.",
                kind=FactorKind.MISSING,
                points=50,
            )
        )
    scope_score = (analysis.seniority_score + analysis.leadership_score) / 2
    score = compensation_score * 0.4 + location.location_score * 0.3 + scope_score * 0.3
    employment = (opening.employment_type or "").casefold()
    if settings.preferred_employment_types and any(
        item.casefold() in employment for item in settings.preferred_employment_types
    ):
        score += 10
        factors.append(
            ScoreFactor(
                dimension=ScoreDimension.VALUE,
                code="preferred_employment_type",
                label="The employment type matches a configured preference.",
                kind=FactorKind.POSITIVE,
                points=10,
                evidence=[opening.employment_type or ""],
            )
        )
    return score


def _apply_gates(
    opening: NormalizedJobOpening,
    analysis: JobFitAnalysis,
    job: JobEnrichment,
    location: LocationAssessment,
    settings: ScoringSettings,
    fit: float,
    response: float,
    value: float,
    gates: list[HardGate],
) -> None:
    if job.relocation_required:
        gates.append(
            HardGate(
                code="relocation_required", label="Relocation-required opportunities are excluded."
            )
        )
    if location.scope is LocationScope.DISTANT and opening.work_arrangement in {
        WorkArrangement.HYBRID,
        WorkArrangement.ON_SITE,
    }:
        gates.append(
            HardGate(
                code="outside_geographic_eligibility",
                label="A distant hybrid or on-site role is outside geographic eligibility.",
                evidence=location.rationale,
            )
        )
    for item in analysis.qualifications:
        if item.gate_category is not GateCategory.NONE and item.match_level in {
            MatchLevel.NONE,
            MatchLevel.UNKNOWN,
        }:
            gates.append(
                HardGate(
                    code=f"required_{item.gate_category.value}:{item.id}",
                    label=f"An explicit required {item.gate_category.value} is not verified.",
                    evidence=[item.job_excerpt],
                )
            )
    compensation = job.compensation_max or job.compensation_min
    if (
        settings.minimum_compensation is not None
        and compensation is not None
        and compensation < settings.minimum_compensation
    ):
        gates.append(
            HardGate(
                code="compensation_below_minimum",
                label="Known compensation is below the configured minimum.",
                evidence=[str(compensation)],
            )
        )
    employment = (opening.employment_type or "").casefold()
    if any(item.casefold() in employment for item in settings.excluded_employment_types):
        gates.append(
            HardGate(
                code="excluded_employment_type",
                label="The employment type is explicitly excluded.",
                evidence=[opening.employment_type or ""],
            )
        )
    for actual, minimum, code, label in (
        (fit, settings.minimum_fit, "fit_below_minimum", "Fit"),
        (
            response,
            settings.minimum_response_likelihood,
            "response_below_minimum",
            "Response likelihood",
        ),
        (value, settings.minimum_opportunity_value, "value_below_minimum", "Opportunity value"),
    ):
        if actual < minimum:
            gates.append(
                HardGate(
                    code=code,
                    label=f"{label} is below the configured minimum.",
                    evidence=[f"{actual:.2f} < {minimum:.2f}"],
                )
            )


def _confidence_score(
    opening: NormalizedJobOpening,
    analysis: JobFitAnalysis,
    job: JobEnrichment,
    location: LocationAssessment,
    factors: list[ScoreFactor],
) -> float:
    direct = any(item.direct_employer_source for item in opening.provenance)
    components = {
        "parser": opening.parser_confidence * 100,
        "provenance": 95.0 if direct else 70.0,
        "date": 100.0 if (opening.posted_at or opening.updated_at) else 40.0,
        "location": location.confidence * 100,
        "fit_analysis": analysis.confidence * 100,
        "description": 100.0
        if len(opening.description) >= 500
        else 70.0
        if len(opening.description) >= 100
        else 40.0,
    }
    score = sum(components.values()) / len(components)
    if job.conflicting_source_data:
        score -= 15
    factors.append(
        ScoreFactor(
            dimension=ScoreDimension.CONFIDENCE,
            code="confidence_components",
            label="Source completeness and evidence quality determine confidence.",
            kind=FactorKind.NEUTRAL,
            points=score,
            detail={"components": components},
        )
    )
    return _clamp(score)


def _confidence_multiplier(confidence: float, settings: ScoringSettings) -> float:
    for band in sorted(settings.confidence_bands, key=lambda item: item.minimum, reverse=True):
        if confidence >= band.minimum:
            return band.multiplier
    return 0.0


def _rule_matches(
    rule: ScoringRule,
    opening: NormalizedJobOpening,
    company: CompanyEnrichment,
) -> bool:
    values = {
        RuleTarget.COMPANY: [opening.company_name],
        RuleTarget.DOMAIN: [opening.company_domain],
        RuleTarget.TITLE: [opening.title],
        RuleTarget.INDUSTRY: company.industries,
        RuleTarget.LOCATION: [opening.location_text or "", *opening.locations],
        RuleTarget.EMPLOYMENT_TYPE: [opening.employment_type or ""],
        RuleTarget.SOURCE: [item.source_id for item in opening.provenance]
        + [item.connector for item in opening.provenance]
        + [item.source_url for item in opening.provenance],
    }[rule.target]
    pattern = rule.pattern.strip().casefold()
    for value in values:
        normalized = value.strip().casefold()
        if rule.match.value == "exact" and normalized == pattern:
            return True
        if rule.match.value == "contains" and pattern in normalized:
            return True
    return False


def _snapshot_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _clamp(value: float) -> float:
    return min(max(float(value), 0.0), 100.0)
