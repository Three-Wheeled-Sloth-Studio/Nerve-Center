"""Local application tracking and opportunity review API."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query

from nerve_center.applications.models import (
    ApplicationEvent,
    ApplicationRecord,
    ApplicationStatus,
    ApplicationUpdate,
    ReviewOpportunity,
)
from nerve_center.persistence.applications import ApplicationRepository
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import (
    CompanyRepository,
    DiscoverySourceRepository,
    JobOpeningRepository,
)
from nerve_center.persistence.scoring import OpportunityScoreRepository
from nerve_center.plugins.job_scout.settings import JobScoutConfigurationStore
from nerve_center.plugins.job_scout.verification import (
    VerificationStatus,
    assess_opening_verification,
    preferred_opportunity_link,
)
from nerve_center.scoring.engine import SCORING_ENGINE_VERSION
from nerve_center.scoring.service import ScoringService

SortKey = Literal["priority", "response", "fit", "freshness"]


def register_application_routes(
    application: FastAPI,
    database: Database,
    *,
    scoring_service: ScoringService | None = None,
    configuration_store: JobScoutConfigurationStore | None = None,
) -> ApplicationRepository:
    applications = ApplicationRepository(database)
    jobs = JobOpeningRepository(database)
    companies = CompanyRepository(database)
    sources = DiscoverySourceRepository(database)
    scores = OpportunityScoreRepository(database)
    application.state.application_repository = applications

    @application.get("/api/v1/applications")
    def list_applications() -> list[ApplicationRecord]:
        return applications.list()

    @application.get("/api/v1/applications/{job_id}")
    def get_application(job_id: str) -> ApplicationRecord:
        _require_job(jobs, job_id)
        return applications.get_or_default(job_id)

    @application.patch("/api/v1/applications/{job_id}")
    def update_application(
        job_id: str,
        request: ApplicationUpdate,
    ) -> ApplicationRecord:
        _require_job(jobs, job_id)
        return applications.save(job_id, request)

    @application.get("/api/v1/applications/{job_id}/events")
    def application_history(job_id: str) -> list[ApplicationEvent]:
        _require_job(jobs, job_id)
        return applications.history(job_id)

    @application.get("/api/v1/review/opportunities")
    def review_opportunities(
        include_dismissed: bool = False,
        sort: SortKey = "priority",
        limit: Annotated[int, Query(ge=1, le=1000)] = 250,
    ) -> list[ReviewOpportunity]:
        items: list[ReviewOpportunity] = []
        configuration = configuration_store.load() if configuration_store else None
        for opening in jobs.list(active_only=False):
            record = applications.get_or_default(opening.id)
            if not include_dismissed and record.status is ApplicationStatus.DISMISSED:
                continue
            verification = assess_opening_verification(opening, sources)
            if (
                verification.status is VerificationStatus.VERIFIED_ABSENT
                and record.status is ApplicationStatus.DISCOVERED
            ):
                continue
            company = companies.get(opening.company_id)
            link = preferred_opportunity_link(opening, company, verification)
            history = scores.list(opening.id)
            if verification.actionable and scoring_service and configuration:
                variant_specs = [
                    (item.document_id, item.label, item.target_titles or configuration.target_titles)
                    for item in configuration.resume_variants
                    if item.active
                ] or [(None, None, configuration.target_titles)]
                current_scores = []
                for resume_document_id, resume_label, target_titles in variant_specs:
                    variant_history = [
                        item
                        for item in history
                        if item.resume_document_id == resume_document_id
                    ]
                    current = next(
                        (
                            item
                            for item in variant_history
                            if item.calculation.get("scoring_engine_version")
                            == SCORING_ENGINE_VERSION
                        ),
                        None,
                    )
                    if current is None and variant_history:
                        try:
                            analysis = scoring_service.fit_analyses.latest(
                                opening.id,
                                resume_document_id=resume_document_id,
                            )
                        except KeyError:
                            analysis = None
                        if analysis is not None:
                            current = scoring_service.score(
                                opening.id,
                                fit_analysis_id=analysis.id,
                            )
                    if current is None:
                        current = scoring_service.ensure_provisional_score(
                            opening.id,
                            intent_terms=[
                                *configuration.target_titles,
                                *configuration.manual_keywords,
                            ],
                            target_titles=target_titles,
                            resume_document_id=resume_document_id,
                            resume_label=resume_label,
                        )
                    current_scores.append(current)
                history = sorted(
                    current_scores,
                    key=lambda item: (item.priority, item.created_at),
                    reverse=True,
                )
            items.append(
                ReviewOpportunity(
                    opening=opening,
                    company=company,
                    score=history[0] if history else None,
                    application=record,
                    next_action=(
                        "Employer-authoritative evidence no longer confirms this role; review before pursuing."
                        if verification.status is VerificationStatus.VERIFIED_ABSENT
                        else _next_action(record.status)
                    ),
                    verification_status=verification.status.value,
                    verification_reason=verification.reason,
                    actionable=verification.actionable,
                    preferred_url=link.url,
                    preferred_url_kind=link.kind,
                    link_warning=link.warning,
                )
            )
        items.sort(key=lambda item: _sort_value(item, sort), reverse=True)
        return items[:limit]

    return applications


def _require_job(repository: JobOpeningRepository, job_id: str) -> None:
    if not any(item.id == job_id for item in repository.list(active_only=False)):
        raise HTTPException(status_code=404, detail=f"unknown job opening: {job_id}")


def _sort_value(item: ReviewOpportunity, sort: SortKey) -> float:
    score = item.score
    if sort == "priority":
        return score.priority if score else -1
    if sort == "response":
        return score.response_likelihood if score else -1
    if sort == "fit":
        return score.fit if score else -1
    timestamp = item.opening.posted_at or item.opening.discovered_at
    return timestamp.timestamp()


def _next_action(status: ApplicationStatus) -> str:
    actions = {
        ApplicationStatus.DISCOVERED: "Review the evidence and decide whether to pursue.",
        ApplicationStatus.SAVED: (
            "Review details or move the opportunity into the application plan."
        ),
        ApplicationStatus.DISMISSED: "Restore the opportunity if circumstances change.",
        ApplicationStatus.PLANNED_TO_APPLY: "Prepare the selected resume and submit manually.",
        ApplicationStatus.APPLYING: "Finish the application and record the submission date.",
        ApplicationStatus.APPLIED: "Wait for a response and record any recruiter contact.",
        ApplicationStatus.RECRUITER_CONTACT: "Prepare for the recruiter conversation.",
        ApplicationStatus.SCREENING: "Prepare for the screening step and capture the outcome.",
        ApplicationStatus.INTERVIEWING: "Prepare for the next interview and capture the outcome.",
        ApplicationStatus.OFFER: "Review the offer and record the final disposition.",
        ApplicationStatus.REJECTED: "Record useful feedback for later scoring calibration.",
        ApplicationStatus.WITHDRAWN: "No action is pending.",
        ApplicationStatus.CLOSED_WITHOUT_RESPONSE: "No action is pending.",
    }
    return actions[status]
