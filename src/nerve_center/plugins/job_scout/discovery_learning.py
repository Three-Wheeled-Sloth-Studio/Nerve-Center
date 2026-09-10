"""Durable Job Scout discovery strategies, coverage, and feedback attribution."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from nerve_center.applications.models import ApplicationStatus
from nerve_center.persistence.application_tables import ApplicationEventModel
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import (
    Base,
    DiscoverySourceModel,
    JobProvenanceModel,
)


class DiscoveryStrategyModel(Base):
    __tablename__ = "job_scout_discovery_strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    identity: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    dimensions: Mapped[dict[str, str]] = mapped_column(JSON)
    origin: Mapped[str] = mapped_column(String(50), index=True)
    learned_weight: Mapped[float] = mapped_column(Float, default=1.0, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    results_examined: Mapped[int] = mapped_column(Integer, default=0)
    companies_discovered: Mapped[int] = mapped_column(Integer, default=0)
    career_sources_resolved: Mapped[int] = mapped_column(Integer, default=0)
    postings_inspected: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_retained: Mapped[int] = mapped_column(Integer, default=0)
    market_relevant_opportunities: Mapped[int] = mapped_column(Integer, default=0)
    positive_feedback: Mapped[float] = mapped_column(Float, default=0.0)
    negative_feedback: Mapped[float] = mapped_column(Float, default=0.0)
    challenge_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_productive_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StrategyAttemptModel(Base):
    __tablename__ = "job_scout_strategy_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    strategy_id: Mapped[str] = mapped_column(
        ForeignKey("job_scout_discovery_strategies.id"), index=True
    )
    cycle: Mapped[int] = mapped_column(Integer, index=True)
    phase: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    results_examined: Mapped[int] = mapped_column(Integer, default=0)
    companies_discovered: Mapped[int] = mapped_column(Integer, default=0)
    career_sources_resolved: Mapped[int] = mapped_column(Integer, default=0)
    postings_inspected: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_retained: Mapped[int] = mapped_column(Integer, default=0)
    market_relevant_opportunities: Mapped[int] = mapped_column(Integer, default=0)
    challenged: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class CompanyDiscoveryEvidenceModel(Base):
    __tablename__ = "job_scout_company_discovery_evidence"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "strategy_id",
            "location_alias",
            name="uq_job_scout_company_strategy_location",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    strategy_id: Mapped[str] = mapped_column(
        ForeignKey("job_scout_discovery_strategies.id"), index=True
    )
    location_alias: Mapped[str] = mapped_column(String(255), default="", index=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    openings_seen: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DiscoveryFeedbackModel(Base):
    __tablename__ = "job_scout_discovery_feedback"
    __table_args__ = (
        UniqueConstraint(
            "application_event_id",
            "strategy_id",
            name="uq_job_scout_feedback_event_strategy",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_event_id: Mapped[str] = mapped_column(String(36), index=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    strategy_id: Mapped[str] = mapped_column(
        ForeignKey("job_scout_discovery_strategies.id"), index=True
    )
    signal: Mapped[str] = mapped_column(String(100), index=True)
    magnitude: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReflectionHypothesisModel(Base):
    __tablename__ = "job_scout_reflection_hypotheses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    cycle: Mapped[int] = mapped_column(Integer, index=True)
    origin: Mapped[str] = mapped_column(String(32), index=True)
    hypothesis: Mapped[str] = mapped_column(String(1000))
    dimensions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    strategy_id: Mapped[str | None] = mapped_column(
        ForeignKey("job_scout_discovery_strategies.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReflectionRequestModel(Base):
    __tablename__ = "job_scout_reflection_requests"

    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    cycle: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DiscoverySessionModel(Base):
    __tablename__ = "job_scout_discovery_sessions"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phase: Mapped[str] = mapped_column(String(32), index=True)
    cycle: Mapped[int] = mapped_column(Integer, default=0)
    no_yield_cycles: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


@dataclass(frozen=True, slots=True)
class DiscoveryStrategySnapshot:
    id: str
    dimensions: dict[str, str]
    origin: str
    learned_weight: float
    attempts: int
    results_examined: int
    companies_discovered: int
    career_sources_resolved: int
    postings_inspected: int
    opportunities_retained: int
    market_relevant_opportunities: int
    positive_feedback: float
    negative_feedback: float
    challenge_count: int
    failure_count: int
    last_attempt_at: datetime | None
    last_productive_at: datetime | None

    @property
    def influence(self) -> str:
        if self.learned_weight >= 1.2:
            return "positive"
        if self.learned_weight < 0.55:
            return "negative"
        if self.learned_weight < 0.85:
            return "deprioritized"
        return "neutral"


@dataclass(frozen=True, slots=True)
class StrategyOutcome:
    status: str = "succeeded"
    results_examined: int = 0
    companies_discovered: int = 0
    career_sources_resolved: int = 0
    postings_inspected: int = 0
    opportunities_retained: int = 0
    market_relevant_opportunities: int = 0
    challenged: int = 0
    failed: int = 0
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def useful_yield(self) -> int:
        return (
            self.companies_discovered
            + self.career_sources_resolved
            + self.opportunities_retained
        )


@dataclass(frozen=True, slots=True)
class DiscoveryCoverageSnapshot:
    run_id: str
    phase: str
    cycle: int
    no_yield_cycles: int
    coverage: dict[str, Any]


DEFAULT_COVERAGE: dict[str, Any] = {
    "strategies_attempted": 0,
    "public_searches_executed": 0,
    "results_examined": 0,
    "companies_discovered": 0,
    "career_sources_resolved": 0,
    "known_company_sources_revisited": 0,
    "postings_inspected": 0,
    "opportunities_retained": 0,
    "market_relevant_opportunities": 0,
    "strategy_changes": 0,
    "reflection_hypotheses": 0,
    "provider_warnings": [],
}


_FEEDBACK_MAGNITUDE = {
    ApplicationStatus.SAVED.value: 0.5,
    ApplicationStatus.DISMISSED.value: -0.4,
    ApplicationStatus.PLANNED_TO_APPLY.value: 0.7,
    ApplicationStatus.APPLYING.value: 0.8,
    ApplicationStatus.APPLIED.value: 1.0,
    ApplicationStatus.RECRUITER_CONTACT.value: 1.5,
    ApplicationStatus.SCREENING.value: 2.0,
    ApplicationStatus.INTERVIEWING.value: 3.0,
    ApplicationStatus.OFFER.value: 4.0,
    ApplicationStatus.REJECTED.value: 0.2,
    ApplicationStatus.WITHDRAWN.value: -0.2,
    ApplicationStatus.CLOSED_WITHOUT_RESPONSE.value: -0.3,
}


class JobScoutDiscoveryRepository:
    """Job Scout-owned durable market-learning state over manager-owned SQLite."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_strategy(
        self,
        dimensions: dict[str, str],
        *,
        origin: str,
        base_weight: float = 1.0,
        now: datetime | None = None,
    ) -> DiscoveryStrategySnapshot:
        normalized, identity, strategy_id = _strategy_identity(dimensions)
        current = now or datetime.now(UTC)
        with self.database.session() as session:
            model = session.scalar(
                select(DiscoveryStrategyModel).where(
                    DiscoveryStrategyModel.identity == identity
                )
            )
            if model is None:
                model = DiscoveryStrategyModel(
                    id=strategy_id,
                    identity=identity,
                    dimensions=normalized,
                    origin=origin,
                    learned_weight=_clamp(base_weight, 0.2, 4.0),
                    created_at=current,
                    updated_at=current,
                )
                session.add(model)
                session.flush()
            return _strategy_snapshot(model)

    def get_strategy(self, strategy_id: str) -> DiscoveryStrategySnapshot:
        with self.database.session() as session:
            model = session.get(DiscoveryStrategyModel, strategy_id)
            if model is None:
                raise KeyError(f"unknown discovery strategy: {strategy_id}")
            return _strategy_snapshot(model)

    def list_strategies(self) -> list[DiscoveryStrategySnapshot]:
        with self.database.session() as session:
            models = session.scalars(
                select(DiscoveryStrategyModel).order_by(
                    DiscoveryStrategyModel.learned_weight.desc(),
                    DiscoveryStrategyModel.created_at,
                )
            ).all()
            return [_strategy_snapshot(item) for item in models]

    def select_strategies(
        self,
        run_id: str,
        *,
        limit: int = 4,
        exploration_floor: float = 0.25,
        excluded_company_ids: set[str] | None = None,
        excluded_source_ids: set[str] | None = None,
        revisit_after_seconds: float | None = None,
        now: datetime | None = None,
    ) -> list[DiscoveryStrategySnapshot]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not 0 <= exploration_floor <= 1:
            raise ValueError("exploration_floor must be between 0 and 1")
        current = now or datetime.now(UTC)
        with self.database.session() as session:
            attempted = set(
                session.scalars(
                    select(StrategyAttemptModel.strategy_id).where(
                        StrategyAttemptModel.run_id == run_id
                    )
                ).all()
            )
            models = session.scalars(select(DiscoveryStrategyModel)).all()
            blocked_companies = excluded_company_ids or set()
            blocked_sources = excluded_source_ids or set()
            candidates = [
                item
                for item in models
                if (
                    item.id not in attempted
                    if revisit_after_seconds is None
                    else item.last_attempt_at is None
                    or current.timestamp() - _utc_sort_value(item.last_attempt_at)
                    >= (
                        revisit_after_seconds
                        if item.dimensions.get("kind") == "public_search"
                        else min(revisit_after_seconds, 3600)
                    )
                )
                and item.dimensions.get("company_id") not in blocked_companies
                and item.dimensions.get("source_id") not in blocked_sources
            ]
            if not candidates:
                return []
            count = min(limit, len(candidates))
            explore_count = 0
            if len(candidates) > 1 and exploration_floor > 0:
                explore_count = min(count, max(1, math.ceil(count * exploration_floor)))
            exploration = sorted(
                candidates,
                key=lambda item: (
                    item.attempts,
                    _utc_sort_value(item.last_attempt_at),
                    item.created_at,
                ),
            )[:explore_count]
            exploration_ids = {item.id for item in exploration}
            exploitation = sorted(
                (item for item in candidates if item.id not in exploration_ids),
                key=lambda item: (_strategy_score(item, current), item.id),
                reverse=True,
            )[: count - len(exploration)]
            selected = [*exploitation, *exploration]
            if count > 1 and not any(
                item.dimensions.get("kind") == "company_revisit" for item in selected
            ):
                company_candidates = sorted(
                    (
                        item
                        for item in candidates
                        if item.dimensions.get("kind") == "company_revisit"
                        and item.id not in {chosen.id for chosen in selected}
                    ),
                    key=lambda item: (_strategy_score(item, current), item.id),
                    reverse=True,
                )
                if company_candidates:
                    selected[-1] = company_candidates[0]
            return [_strategy_snapshot(item) for item in selected]

    def record_attempt(
        self,
        run_id: str,
        cycle: int,
        strategy_id: str,
        phase: str,
        outcome: StrategyOutcome,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> DiscoveryStrategySnapshot:
        finished = finished_at or datetime.now(UTC)
        started = started_at or finished
        with self.database.session() as session:
            model = session.get(DiscoveryStrategyModel, strategy_id)
            if model is None:
                raise KeyError(f"unknown discovery strategy: {strategy_id}")
            session.add(
                StrategyAttemptModel(
                    id=str(uuid4()),
                    run_id=run_id,
                    strategy_id=strategy_id,
                    cycle=cycle,
                    phase=phase,
                    started_at=started,
                    finished_at=finished,
                    status=outcome.status,
                    results_examined=outcome.results_examined,
                    companies_discovered=outcome.companies_discovered,
                    career_sources_resolved=outcome.career_sources_resolved,
                    postings_inspected=outcome.postings_inspected,
                    opportunities_retained=outcome.opportunities_retained,
                    market_relevant_opportunities=outcome.market_relevant_opportunities,
                    challenged=outcome.challenged,
                    failed=outcome.failed,
                    detail=outcome.detail,
                )
            )
            model.attempts += 1
            model.results_examined += outcome.results_examined
            model.companies_discovered += outcome.companies_discovered
            model.career_sources_resolved += outcome.career_sources_resolved
            model.postings_inspected += outcome.postings_inspected
            model.opportunities_retained += outcome.opportunities_retained
            model.market_relevant_opportunities += outcome.market_relevant_opportunities
            model.challenge_count += outcome.challenged
            model.failure_count += outcome.failed
            model.last_attempt_at = finished
            location_conditioned = bool(model.dimensions.get("location"))
            productive_yield = (
                outcome.market_relevant_opportunities
                if location_conditioned
                else outcome.useful_yield
            )
            if productive_yield > 0:
                model.last_productive_at = finished
            target = _attempt_target_weight(
                outcome,
                location_conditioned=location_conditioned,
            )
            model.learned_weight = _clamp(model.learned_weight * 0.8 + target * 0.2, 0.2, 4.0)
            model.updated_at = finished
            session.flush()
            return _strategy_snapshot(model)

    def record_company_evidence(
        self,
        company_id: str,
        strategy_id: str,
        *,
        location_alias: str = "",
        provenance: dict[str, Any] | None = None,
        openings_seen: int = 0,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        location = location_alias.strip()
        evidence_id = str(
            uuid5(
                NAMESPACE_URL,
                f"nerve-center/job-scout/company/{company_id}/{strategy_id}/{location.casefold()}",
            )
        )
        with self.database.session() as session:
            model = session.scalar(
                select(CompanyDiscoveryEvidenceModel).where(
                    CompanyDiscoveryEvidenceModel.company_id == company_id,
                    CompanyDiscoveryEvidenceModel.strategy_id == strategy_id,
                    CompanyDiscoveryEvidenceModel.location_alias == location,
                )
            )
            if model is None:
                session.add(
                    CompanyDiscoveryEvidenceModel(
                        id=evidence_id,
                        company_id=company_id,
                        strategy_id=strategy_id,
                        location_alias=location,
                        provenance=provenance or {},
                        openings_seen=max(openings_seen, 0),
                        first_seen_at=current,
                        last_seen_at=current,
                    )
                )
            else:
                model.last_seen_at = current
                model.openings_seen += max(openings_seen, 0)
                if provenance:
                    model.provenance = {**model.provenance, **provenance}

    def company_evidence_count(self, company_id: str) -> int:
        with self.database.session() as session:
            return len(
                session.scalars(
                    select(CompanyDiscoveryEvidenceModel).where(
                        CompanyDiscoveryEvidenceModel.company_id == company_id
                    )
                ).all()
            )

    def sync_application_feedback(self) -> int:
        applied = 0
        with self.database.session() as session:
            events = session.scalars(
                select(ApplicationEventModel).order_by(ApplicationEventModel.created_at)
            ).all()
            for event in events:
                magnitude = _FEEDBACK_MAGNITUDE.get(event.to_status)
                if magnitude is None or magnitude == 0:
                    continue
                strategy_ids = _strategy_ids_for_job(session, event.job_id)
                for strategy_id in strategy_ids:
                    existing = session.scalar(
                        select(DiscoveryFeedbackModel).where(
                            DiscoveryFeedbackModel.application_event_id == event.id,
                            DiscoveryFeedbackModel.strategy_id == strategy_id,
                        )
                    )
                    strategy = session.get(DiscoveryStrategyModel, strategy_id)
                    if existing is not None or strategy is None:
                        continue
                    session.add(
                        DiscoveryFeedbackModel(
                            id=str(uuid4()),
                            application_event_id=event.id,
                            job_id=event.job_id,
                            strategy_id=strategy_id,
                            signal=f"application:{event.to_status}",
                            magnitude=magnitude,
                            created_at=event.created_at,
                        )
                    )
                    if magnitude > 0:
                        strategy.positive_feedback += magnitude
                    else:
                        strategy.negative_feedback += abs(magnitude)
                    strategy.learned_weight = _clamp(
                        strategy.learned_weight + magnitude * 0.08,
                        0.2,
                        4.0,
                    )
                    strategy.updated_at = event.created_at
                    applied += 1
        return applied

    def update_session(
        self,
        run_id: str,
        *,
        phase: str | None = None,
        cycle: int | None = None,
        no_yield_cycles: int | None = None,
        increments: dict[str, int] | None = None,
        warnings: list[str] | None = None,
        now: datetime | None = None,
    ) -> DiscoveryCoverageSnapshot:
        current = now or datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(DiscoverySessionModel, run_id)
            if model is None:
                model = DiscoverySessionModel(
                    run_id=run_id,
                    phase=phase or "expand",
                    cycle=cycle or 0,
                    no_yield_cycles=no_yield_cycles or 0,
                    coverage=_new_coverage(),
                    started_at=current,
                    updated_at=current,
                )
                session.add(model)
                session.flush()
            coverage = _merge_coverage(model.coverage, increments, warnings)
            model.coverage = coverage
            if phase is not None:
                model.phase = phase
            if cycle is not None:
                model.cycle = cycle
            if no_yield_cycles is not None:
                model.no_yield_cycles = no_yield_cycles
            model.updated_at = current
            session.flush()
            return _coverage_snapshot(model)

    def session(self, run_id: str) -> DiscoveryCoverageSnapshot:
        with self.database.session() as session:
            model = session.get(DiscoverySessionModel, run_id)
            if model is None:
                raise KeyError(f"unknown discovery session: {run_id}")
            return _coverage_snapshot(model)

    def record_reflection_hypothesis(
        self,
        run_id: str,
        cycle: int,
        *,
        origin: str,
        hypothesis: str,
        dimensions: dict[str, str],
        strategy_id: str | None = None,
        now: datetime | None = None,
    ) -> str:
        current = now or datetime.now(UTC)
        hypothesis_id = str(uuid4())
        with self.database.session() as session:
            session.add(
                ReflectionHypothesisModel(
                    id=hypothesis_id,
                    run_id=run_id,
                    cycle=cycle,
                    origin=origin,
                    hypothesis=hypothesis[:1000],
                    dimensions=dimensions,
                    strategy_id=strategy_id,
                    created_at=current,
                )
            )
        self.update_session(
            run_id,
            increments={"reflection_hypotheses": 1},
            now=current,
        )
        return hypothesis_id

    def reflection_hypotheses(self, run_id: str) -> list[dict[str, Any]]:
        with self.database.session() as session:
            models = session.scalars(
                select(ReflectionHypothesisModel)
                .where(ReflectionHypothesisModel.run_id == run_id)
                .order_by(ReflectionHypothesisModel.created_at)
            ).all()
            return [
                {
                    "id": item.id,
                    "origin": item.origin,
                    "hypothesis": item.hypothesis,
                    "dimensions": dict(item.dimensions),
                    "strategy_id": item.strategy_id,
                }
                for item in models
            ]

    def record_reflection_request(
        self,
        request_id: str,
        run_id: str,
        cycle: int,
        *,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        with self.database.session() as session:
            if session.get(ReflectionRequestModel, request_id) is None:
                session.add(
                    ReflectionRequestModel(
                        request_id=request_id,
                        run_id=run_id,
                        cycle=cycle,
                        status="queued",
                        created_at=current,
                    )
                )

    def reflection_request(self, request_id: str) -> dict[str, Any] | None:
        with self.database.session() as session:
            model = session.get(ReflectionRequestModel, request_id)
            if model is None:
                return None
            return {
                "request_id": model.request_id,
                "run_id": model.run_id,
                "cycle": model.cycle,
                "status": model.status,
            }

    def mark_reflection_applied(
        self,
        request_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(ReflectionRequestModel, request_id)
            if model is None:
                raise KeyError(f"unknown reflection request: {request_id}")
            model.status = "applied"
            model.applied_at = current


def _strategy_identity(dimensions: dict[str, str]) -> tuple[dict[str, str], str, str]:
    normalized = {
        str(key).strip(): " ".join(str(value).split()).strip()
        for key, value in dimensions.items()
        if str(key).strip() and " ".join(str(value).split()).strip()
    }
    if not normalized:
        raise ValueError("a discovery strategy needs at least one dimension")
    canonical = json.dumps(
        {key.casefold(): value.casefold() for key, value in normalized.items()},
        sort_keys=True,
        separators=(",", ":"),
    )
    identity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    strategy_id = str(
        uuid5(NAMESPACE_URL, f"nerve-center/job-scout/discovery-strategy/{canonical}")
    )
    return normalized, identity, strategy_id


def _strategy_snapshot(model: DiscoveryStrategyModel) -> DiscoveryStrategySnapshot:
    return DiscoveryStrategySnapshot(
        id=model.id,
        dimensions=dict(model.dimensions),
        origin=model.origin,
        learned_weight=float(model.learned_weight),
        attempts=model.attempts,
        results_examined=model.results_examined,
        companies_discovered=model.companies_discovered,
        career_sources_resolved=model.career_sources_resolved,
        postings_inspected=model.postings_inspected,
        opportunities_retained=model.opportunities_retained,
        market_relevant_opportunities=model.market_relevant_opportunities,
        positive_feedback=float(model.positive_feedback),
        negative_feedback=float(model.negative_feedback),
        challenge_count=model.challenge_count,
        failure_count=model.failure_count,
        last_attempt_at=_as_utc_optional(model.last_attempt_at),
        last_productive_at=_as_utc_optional(model.last_productive_at),
    )


def _coverage_snapshot(model: DiscoverySessionModel) -> DiscoveryCoverageSnapshot:
    return DiscoveryCoverageSnapshot(
        run_id=model.run_id,
        phase=model.phase,
        cycle=model.cycle,
        no_yield_cycles=model.no_yield_cycles,
        coverage=_merge_coverage(model.coverage),
    )


def _new_coverage() -> dict[str, Any]:
    return {**DEFAULT_COVERAGE, "provider_warnings": []}


def _merge_coverage(
    current: dict[str, Any] | None,
    increments: dict[str, int] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    merged = _new_coverage()
    if current:
        merged.update(current)
        merged["provider_warnings"] = list(current.get("provider_warnings", []))
    for key, value in (increments or {}).items():
        if key not in merged or key == "provider_warnings":
            continue
        merged[key] = int(merged.get(key, 0)) + int(value)
    if warnings:
        known = {str(item) for item in merged["provider_warnings"]}
        for warning in warnings:
            text = " ".join(str(warning).split())[:500]
            if text and text not in known:
                merged["provider_warnings"].append(text)
                known.add(text)
    return merged


def _strategy_ids_for_job(session: Any, job_id: str) -> set[str]:
    provenance = session.scalars(
        select(JobProvenanceModel).where(JobProvenanceModel.job_id == job_id)
    ).all()
    source_ids = {item.source_id for item in provenance}
    if not source_ids:
        return set()
    sources = session.scalars(
        select(DiscoverySourceModel).where(DiscoverySourceModel.id.in_(source_ids))
    ).all()
    strategy_ids: set[str] = set()
    for source in sources:
        configuration = source.configuration if isinstance(source.configuration, dict) else {}
        values = configuration.get("discovery_strategy_ids", [])
        if isinstance(values, list):
            strategy_ids.update(str(item) for item in values if str(item).strip())
    return strategy_ids


def _attempt_target_weight(
    outcome: StrategyOutcome,
    *,
    location_conditioned: bool = False,
) -> float:
    if location_conditioned:
        useful = outcome.market_relevant_opportunities * 0.8
        penalties = outcome.challenged * 0.6 + outcome.failed * 0.3
        if useful == 0 and penalties == 0:
            return 0.75
        return _clamp(1.0 + useful - penalties, 0.2, 4.0)
    useful = (
        outcome.opportunities_retained * 0.8
        + outcome.career_sources_resolved * 0.5
        + outcome.companies_discovered * 0.35
        + min(outcome.postings_inspected, 25) * 0.02
    )
    penalties = outcome.challenged * 0.6 + outcome.failed * 0.3
    if useful == 0 and penalties == 0:
        return 0.85
    return _clamp(1.0 + useful - penalties, 0.2, 4.0)


def _strategy_score(model: DiscoveryStrategyModel, now: datetime) -> float:
    attempts = max(model.attempts, 1)
    if model.dimensions.get("location"):
        productivity = model.market_relevant_opportunities * 1.5 / attempts
    else:
        productivity = (
            model.opportunities_retained * 1.5
            + model.career_sources_resolved
            + model.companies_discovered * 0.75
        ) / attempts
    health_penalty = (model.challenge_count * 0.7 + model.failure_count * 0.4) / attempts
    feedback = (model.positive_feedback - model.negative_feedback) * 0.15
    staleness = 0.2 if model.last_attempt_at is None else 0.0
    if model.last_attempt_at is not None:
        age_days = (now - _as_utc(model.last_attempt_at)).total_seconds() / 86400
        if age_days >= 7:
            staleness = 0.2
        elif age_days >= 2:
            staleness = 0.1
    return float(model.learned_weight) + productivity + feedback + staleness - health_penalty


def _utc_sort_value(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return _as_utc(value).timestamp()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _as_utc_optional(value: datetime | None) -> datetime | None:
    return _as_utc(value) if value is not None else None


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
