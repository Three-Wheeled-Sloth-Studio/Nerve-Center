"""Durable local-only Model Lab corpus, exploration, and benchmark history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from nerve_center.persistence.database import Database
from nerve_center.persistence.models import (
    Base,
    ModelObservationModel,
    WorkRequestModel,
    WorkResultModel,
)


class ModelLabSettingsModel(Base):
    __tablename__ = "core_model_lab_settings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    capture_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    excluded_modules: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BenchmarkCorpusModel(Base):
    __tablename__ = "core_model_lab_corpus"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    module_id: Mapped[str] = mapped_column(String(100), index=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    work_request_id: Mapped[str] = mapped_column(String(36), index=True)
    contract_version: Mapped[str] = mapped_column(String(100))
    system_prompt: Mapped[str] = mapped_column(Text)
    user_prompt: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON)
    requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    expected_output: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSON)
    production_provider: Mapped[str | None] = mapped_column(String(50))
    production_model: Mapped[str | None] = mapped_column(String(200))
    production_call_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ModelLabSessionModel(Base):
    __tablename__ = "core_model_lab_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    max_attempts: Mapped[int] = mapped_column(Integer)
    attempts_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BenchmarkResultModel(Base):
    __tablename__ = "core_model_lab_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    corpus_id: Mapped[str] = mapped_column(ForeignKey("core_model_lab_corpus.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("core_model_lab_sessions.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    schema_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    output: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100))
    provider_call_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


@dataclass(frozen=True, slots=True)
class ModelLabSettingsSnapshot:
    enabled: bool
    capture_enabled: bool
    excluded_modules: tuple[str, ...]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CompletedLlmWork:
    request_id: str
    module_id: str
    run_id: str
    task_id: str
    payload: dict[str, Any]
    output_contract: dict[str, Any]
    requirements: dict[str, Any]
    result_payload: dict[str, Any]
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class BenchmarkCorpusItem:
    id: str
    fingerprint: str
    module_id: str
    task_id: str
    run_id: str
    work_request_id: str
    contract_version: str
    system_prompt: str
    user_prompt: str
    output_schema: dict[str, Any]
    requirements: dict[str, Any]
    expected_output: dict[str, Any] | list[Any]
    production_provider: str | None
    production_model: str | None
    production_call_id: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ModelLabSessionSnapshot:
    id: str
    status: str
    starts_at: datetime
    ends_at: datetime
    max_attempts: int
    attempts_used: int
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class BenchmarkResultSnapshot:
    id: str
    corpus_id: str
    session_id: str
    provider: str
    model: str
    status: str
    schema_valid: bool | None
    duration_ms: int
    output: dict[str, Any] | list[Any] | None
    error_code: str | None
    provider_call_id: str | None
    created_at: datetime


class ModelLabRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def settings(self) -> ModelLabSettingsSnapshot:
        with self.database.session() as session:
            model = session.get(ModelLabSettingsModel, "default")
            if model is None:
                model = ModelLabSettingsModel(
                    id="default",
                    enabled=True,
                    capture_enabled=True,
                    excluded_modules=[],
                    updated_at=datetime.now(UTC),
                )
                session.add(model)
                session.flush()
            return _settings(model)

    def update_settings(
        self,
        *,
        enabled: bool,
        capture_enabled: bool,
        excluded_modules: list[str],
    ) -> ModelLabSettingsSnapshot:
        excluded = sorted({item.strip() for item in excluded_modules if item.strip()})
        with self.database.session() as session:
            model = session.get(ModelLabSettingsModel, "default")
            if model is None:
                model = ModelLabSettingsModel(id="default", updated_at=datetime.now(UTC))
                session.add(model)
            model.enabled = enabled
            model.capture_enabled = capture_enabled
            model.excluded_modules = excluded
            model.updated_at = datetime.now(UTC)
            session.flush()
            return _settings(model)

    def completed_llm_work(self, limit: int = 5000) -> list[CompletedLlmWork]:
        statement = (
            select(WorkRequestModel, WorkResultModel)
            .join(WorkResultModel, WorkResultModel.request_id == WorkRequestModel.id)
            .where(WorkRequestModel.work_class == "llm")
            .order_by(WorkResultModel.created_at.asc())
            .limit(limit)
        )
        with self.database.session() as session:
            rows = session.execute(statement).all()
            return [
                CompletedLlmWork(
                    request_id=request.id,
                    module_id=request.module_id,
                    run_id=request.run_id,
                    task_id=request.task_id,
                    payload=dict(request.payload),
                    output_contract=dict(request.output_contract),
                    requirements=dict(request.requirements),
                    result_payload=dict(result.payload),
                    completed_at=result.created_at,
                )
                for request, result in rows
            ]

    def add_corpus(
        self,
        *,
        fingerprint: str,
        module_id: str,
        task_id: str,
        run_id: str,
        work_request_id: str,
        contract_version: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict[str, Any],
        requirements: dict[str, Any],
        expected_output: dict[str, Any] | list[Any],
        production_provider: str | None,
        production_model: str | None,
        production_call_id: str | None,
        created_at: datetime,
    ) -> tuple[BenchmarkCorpusItem, bool]:
        with self.database.session() as session:
            existing = session.scalar(
                select(BenchmarkCorpusModel).where(
                    BenchmarkCorpusModel.fingerprint == fingerprint
                )
            )
            if existing is not None:
                return _corpus(existing), False
            model = BenchmarkCorpusModel(
                id=str(uuid4()),
                fingerprint=fingerprint,
                module_id=module_id,
                task_id=task_id,
                run_id=run_id,
                work_request_id=work_request_id,
                contract_version=contract_version,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                output_schema=output_schema,
                requirements=requirements,
                expected_output=expected_output,
                production_provider=production_provider,
                production_model=production_model,
                production_call_id=production_call_id,
                created_at=_utc(created_at),
            )
            session.add(model)
            session.flush()
            return _corpus(model), True

    def list_corpus(self, limit: int = 200) -> list[BenchmarkCorpusItem]:
        with self.database.session() as session:
            items = session.scalars(
                select(BenchmarkCorpusModel)
                .order_by(BenchmarkCorpusModel.created_at.desc())
                .limit(limit)
            ).all()
            return [_corpus(item) for item in items]

    def get_corpus(self, corpus_id: str) -> BenchmarkCorpusItem:
        with self.database.session() as session:
            model = session.get(BenchmarkCorpusModel, corpus_id)
            if model is None:
                raise KeyError(f"benchmark corpus item {corpus_id!r} was not found")
            return _corpus(model)

    def corpus_count(self) -> int:
        with self.database.session() as session:
            return len(session.scalars(select(BenchmarkCorpusModel.id)).all())

    def task_ids(self) -> list[str]:
        with self.database.session() as session:
            return sorted(
                {
                    str(item)
                    for item in session.scalars(
                        select(ModelObservationModel.task_id).distinct()
                    ).all()
                }
            )

    def start_session(
        self,
        duration_seconds: int,
        max_attempts: int,
        now: datetime | None = None,
    ) -> ModelLabSessionSnapshot:
        current = _utc(now)
        active = self.active_session(current)
        if active is not None:
            raise ValueError(f"Model Lab exploration session {active.id} is already active")
        with self.database.session() as session:
            model = ModelLabSessionModel(
                id=str(uuid4()),
                status="running",
                starts_at=current,
                ends_at=current + timedelta(seconds=duration_seconds),
                max_attempts=max_attempts,
                attempts_used=0,
                created_at=current,
                finished_at=None,
            )
            session.add(model)
            session.flush()
            return _lab_session(model)

    def active_session(self, now: datetime | None = None) -> ModelLabSessionSnapshot | None:
        current = _utc(now)
        with self.database.session() as session:
            model = session.scalar(
                select(ModelLabSessionModel)
                .where(ModelLabSessionModel.status == "running")
                .order_by(ModelLabSessionModel.starts_at.desc())
                .limit(1)
            )
            if model is None:
                return None
            if model.ends_at <= current or model.attempts_used >= model.max_attempts:
                model.status = "completed"
                model.finished_at = current
                session.flush()
                return None
            return _lab_session(model)

    def consume_attempt(
        self, session_id: str, now: datetime | None = None
    ) -> ModelLabSessionSnapshot:
        current = _utc(now)
        with self.database.session() as session:
            model = session.get(ModelLabSessionModel, session_id)
            if model is None:
                raise KeyError(f"Model Lab exploration session {session_id!r} was not found")
            if model.status != "running" or model.ends_at <= current:
                raise ValueError("Model Lab exploration window is closed")
            if model.attempts_used >= model.max_attempts:
                raise ValueError("Model Lab exploration budget is exhausted")
            model.attempts_used += 1
            if model.attempts_used >= model.max_attempts:
                model.status = "completed"
                model.finished_at = current
            session.flush()
            return _lab_session(model)

    def latest_session(self) -> ModelLabSessionSnapshot | None:
        with self.database.session() as session:
            model = session.scalar(
                select(ModelLabSessionModel)
                .order_by(ModelLabSessionModel.created_at.desc())
                .limit(1)
            )
            return _lab_session(model) if model is not None else None

    def record_result(
        self,
        *,
        corpus_id: str,
        session_id: str,
        provider: str,
        model: str,
        status: str,
        schema_valid: bool | None,
        duration_ms: int,
        output: dict[str, Any] | list[Any] | None,
        error_code: str | None,
        provider_call_id: str | None,
        now: datetime | None = None,
    ) -> BenchmarkResultSnapshot:
        with self.database.session() as session:
            model_row = BenchmarkResultModel(
                id=str(uuid4()),
                corpus_id=corpus_id,
                session_id=session_id,
                provider=provider,
                model=model,
                status=status,
                schema_valid=schema_valid,
                duration_ms=max(duration_ms, 0),
                output=output,
                error_code=error_code,
                provider_call_id=provider_call_id,
                created_at=_utc(now),
            )
            session.add(model_row)
            session.flush()
            return _result(model_row)

    def list_results(self, limit: int = 200) -> list[BenchmarkResultSnapshot]:
        with self.database.session() as session:
            items = session.scalars(
                select(BenchmarkResultModel)
                .order_by(BenchmarkResultModel.created_at.desc())
                .limit(limit)
            ).all()
            return [_result(item) for item in items]


def _settings(model: ModelLabSettingsModel) -> ModelLabSettingsSnapshot:
    return ModelLabSettingsSnapshot(
        enabled=model.enabled,
        capture_enabled=model.capture_enabled,
        excluded_modules=tuple(model.excluded_modules or []),
        updated_at=_utc(model.updated_at),
    )


def _corpus(model: BenchmarkCorpusModel) -> BenchmarkCorpusItem:
    return BenchmarkCorpusItem(
        id=model.id,
        fingerprint=model.fingerprint,
        module_id=model.module_id,
        task_id=model.task_id,
        run_id=model.run_id,
        work_request_id=model.work_request_id,
        contract_version=model.contract_version,
        system_prompt=model.system_prompt,
        user_prompt=model.user_prompt,
        output_schema=dict(model.output_schema),
        requirements=dict(model.requirements or {}),
        expected_output=model.expected_output,
        production_provider=model.production_provider,
        production_model=model.production_model,
        production_call_id=model.production_call_id,
        created_at=_utc(model.created_at),
    )


def _lab_session(model: ModelLabSessionModel) -> ModelLabSessionSnapshot:
    return ModelLabSessionSnapshot(
        id=model.id,
        status=model.status,
        starts_at=_utc(model.starts_at),
        ends_at=_utc(model.ends_at),
        max_attempts=model.max_attempts,
        attempts_used=model.attempts_used,
        created_at=_utc(model.created_at),
        finished_at=_utc(model.finished_at) if model.finished_at else None,
    )


def _result(model: BenchmarkResultModel) -> BenchmarkResultSnapshot:
    return BenchmarkResultSnapshot(
        id=model.id,
        corpus_id=model.corpus_id,
        session_id=model.session_id,
        provider=model.provider,
        model=model.model,
        status=model.status,
        schema_valid=model.schema_valid,
        duration_ms=model.duration_ms,
        output=model.output,
        error_code=model.error_code,
        provider_call_id=model.provider_call_id,
        created_at=_utc(model.created_at),
    )


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        return current.replace(tzinfo=UTC)
    return current.astimezone(UTC)
