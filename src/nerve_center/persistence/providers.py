"""Secret-safe provider call metadata persistence."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Integer, case, func, select

from nerve_center.persistence.database import Database
from nerve_center.persistence.models import (
    ModelObservationModel,
    ProviderCallModel,
    ProviderModelCatalogModel,
)
from nerve_center.providers.base import ProviderCallMetadata, ProviderModel


@dataclass(frozen=True, slots=True)
class TaskModelEvidence:
    provider: str
    model: str
    attempts: int
    success_rate: float
    schema_valid_rate: float
    acceptance_rate: float | None
    average_duration_ms: float


@dataclass(frozen=True, slots=True)
class ProviderCatalogEntry:
    provider: str
    model: str
    label: str
    family: str | None
    parameter_size: str | None
    quantization: str | None
    installed: bool
    capabilities: dict[str, object]
    hardware_fit: dict[str, object]
    last_seen_at: datetime


class ProviderCallRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def record(self, metadata: ProviderCallMetadata) -> None:
        with self.database.session() as session:
            session.add(
                ProviderCallModel(
                    id=metadata.id,
                    provider=metadata.provider,
                    model=metadata.model,
                    contract_version=metadata.contract_version,
                    response_schema=metadata.response_schema,
                    started_at=metadata.started_at,
                    duration_ms=metadata.duration_ms,
                    status=metadata.status,
                    error_code=metadata.error_code,
                    retry_count=metadata.retry_count,
                    input_char_count=metadata.input_char_count,
                    output_char_count=metadata.output_char_count,
                    prompt_eval_count=metadata.prompt_eval_count,
                    eval_count=metadata.eval_count,
                )
            )


class ModelEvidenceRepository:
    """Durable model catalog and task-specific routing observations."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def sync_models(self, provider: str, models: list[ProviderModel]) -> None:
        now = datetime.now(UTC)
        seen = {item.id for item in models}
        hardware = {
            "status": "observed",
            "system": platform.system(),
            "architecture": platform.machine(),
            "logical_cpu_count": os.cpu_count(),
            "memory_fit": "unmeasured",
            "accelerator_fit": "unmeasured",
        }
        with self.database.session() as session:
            existing = {
                item.model: item
                for item in session.scalars(
                    select(ProviderModelCatalogModel).where(
                        ProviderModelCatalogModel.provider == provider
                    )
                ).all()
            }
            for model in models:
                item = existing.get(model.id)
                if item is None:
                    item = ProviderModelCatalogModel(
                        id=str(uuid4()),
                        provider=provider,
                        model=model.id,
                        label=model.label,
                        capabilities={"structured_output": True, "modalities": ["text"]},
                        hardware_fit=hardware,
                        last_seen_at=now,
                    )
                    session.add(item)
                item.label = model.label
                item.family = model.family
                item.parameter_size = model.parameter_size
                item.quantization = model.quantization
                item.provider_modified_at = model.modified_at
                item.installed = True
                item.hardware_fit = hardware
                item.last_seen_at = now
            for model_id, item in existing.items():
                if model_id not in seen:
                    item.installed = False

    def list_models(self) -> list[ProviderCatalogEntry]:
        with self.database.session() as session:
            items = session.scalars(
                select(ProviderModelCatalogModel).order_by(
                    ProviderModelCatalogModel.provider,
                    ProviderModelCatalogModel.model,
                )
            ).all()
            return [
                ProviderCatalogEntry(
                    provider=item.provider,
                    model=item.model,
                    label=item.label,
                    family=item.family,
                    parameter_size=item.parameter_size,
                    quantization=item.quantization,
                    installed=item.installed,
                    capabilities=dict(item.capabilities),
                    hardware_fit=dict(item.hardware_fit),
                    last_seen_at=item.last_seen_at,
                )
                for item in items
            ]

    def record_outcome(
        self,
        *,
        task_id: str,
        provider: str,
        model: str,
        status: str,
        duration_ms: int,
        retry_count: int = 0,
        provider_call_id: str | None = None,
        work_request_id: str | None = None,
        schema_valid: bool | None = None,
        error_code: str | None = None,
    ) -> None:
        with self.database.session() as session:
            if provider_call_id is not None:
                duplicate = session.scalar(
                    select(ModelObservationModel).where(
                        ModelObservationModel.provider_call_id == provider_call_id
                    )
                )
                if duplicate is not None:
                    duplicate.work_request_id = work_request_id or duplicate.work_request_id
                    duplicate.schema_valid = schema_valid
                    duplicate.status = status
                    duplicate.error_code = error_code
                    return
            session.add(
                ModelObservationModel(
                    id=str(uuid4()),
                    provider_call_id=provider_call_id,
                    work_request_id=work_request_id,
                    task_id=task_id,
                    provider=provider,
                    model=model,
                    status=status,
                    duration_ms=max(duration_ms, 0),
                    retry_count=max(retry_count, 0),
                    schema_valid=schema_valid,
                    accepted=None,
                    error_code=error_code,
                    observed_at=datetime.now(UTC),
                )
            )

    def mark_disposition(
        self, provider_call_id: str, *, accepted: bool, reason: str | None = None
    ) -> None:
        with self.database.session() as session:
            observation = session.scalar(
                select(ModelObservationModel).where(
                    ModelObservationModel.provider_call_id == provider_call_id
                )
            )
            if observation is not None:
                observation.accepted = accepted
                observation.disposition_reason = reason

    def task_evidence(self, task_id: str) -> list[TaskModelEvidence]:
        with self.database.session() as session:
            rows = session.execute(
                select(
                    ModelObservationModel.provider,
                    ModelObservationModel.model,
                    func.count(ModelObservationModel.id),
                    func.avg(func.cast(ModelObservationModel.status == "succeeded", Integer)),
                    func.avg(func.cast(ModelObservationModel.schema_valid.is_(True), Integer)),
                    func.avg(
                        case(
                            (
                                ModelObservationModel.accepted.is_not(None),
                                func.cast(ModelObservationModel.accepted.is_(True), Integer),
                            ),
                            else_=None,
                        )
                    ),
                    func.avg(ModelObservationModel.duration_ms),
                    func.count(ModelObservationModel.accepted),
                )
                .where(ModelObservationModel.task_id == task_id)
                .group_by(ModelObservationModel.provider, ModelObservationModel.model)
            ).all()
        return [
            TaskModelEvidence(
                provider=row[0],
                model=row[1],
                attempts=int(row[2]),
                success_rate=float(row[3] or 0),
                schema_valid_rate=float(row[4] or 0),
                acceptance_rate=float(row[5]) if row[7] else None,
                average_duration_ms=float(row[6] or 0),
            )
            for row in rows
        ]
