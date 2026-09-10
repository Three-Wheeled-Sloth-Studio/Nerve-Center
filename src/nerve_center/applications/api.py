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
from nerve_center.discovery.models import NormalizedJobOpening, WorkArrangement
from nerve_center.persistence.applications import ApplicationRepository
from nerve_center.persistence.database import Database
from nerve_center.persistence.discovery import CompanyRepository, JobOpeningRepository
from nerve_center.persistence.scoring import OpportunityScoreRepository
from nerve_center.plugins.job_scout.settings import JobScoutConfigurationStore
from nerve_center.scoring.engine import SCORING_ENGINE_VERSION
from nerve_center.scoring.location import opening_matches_markets
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
            if configuration and not _matches_review_geography(opening, configuration.locations):
                continue
            record = applications.get_or_default(opening.id)
            if not include_dismissed and record.status is ApplicationStatus.DISMISSED:
                continue
            history = scores.list(opening.id)
            latest_fit_contract = (
                str(history[0].calculation.get("fit_contract_version") or "")
                if history
                else ""
            )
            if (
                history
                and scoring_service
                and configuration
                and not latest_fit_contract.startswith("job-fit-provisional-")
                and history[0].calculation.get("scoring_engine_version")
                != SCORING_ENGINE_VERSION
            ):
                history = [scoring_service.score(opening.id)]
                latest_fit_contract = str(
                    history[0].calculation.get("fit_contract_version") or ""
                )
            if scoring_service and configuration and (
                not history or latest_fit_contract.startswith("job-fit-provisional-")
            ):
                history = [
                    scoring_service.ensure_provisional_score(
                        opening.id,
                        intent_terms=[*configuration.target_titles, *configuration.manual_keywords],
                        target_titles=configuration.target_titles,
                    )
                ]
            items.append(
                ReviewOpportunity(
                    opening=opening,
                    company=companies.get(opening.company_id),
                    score=history[0] if history else None,
                    application=record,
                    next_action=_next_action(record.status),
                )
            )
        items.sort(key=lambda item: _sort_value(item, sort), reverse=True)
        return items[:limit]

    return applications


def _matches_review_geography(
    opening: NormalizedJobOpening, configured_locations: list[str]
) -> bool:
    if opening.work_arrangement is WorkArrangement.REMOTE:
        return True
    if not configured_locations:
        return True
    if opening_matches_markets(opening, configured_locations):
        return True
    location = " ".join([opening.location_text or "", *opening.locations]).casefold()
    if opening.work_arrangement in {WorkArrangement.HYBRID, WorkArrangement.ON_SITE}:
        return False
    normalized = location.strip(" ,;")
    nationwide = {"", "usa", "united states", "united states of america"}
    return normalized in nationwide or "remote" in normalized


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
