"""Pure-read projection over durable manager-owned summary evidence."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from nerve_center.attention.domain import AttentionKind, AttentionState
from nerve_center.persistence.attention import AttentionItemModel
from nerve_center.persistence.code_shop import CodeShopAttemptModel, CodeShopTaskModel
from nerve_center.persistence.database import Database
from nerve_center.persistence.model_lab import BenchmarkCorpusModel, BenchmarkResultModel
from nerve_center.persistence.models import ModuleModel, RunModel, WorkRequestModel
from nerve_center.summary.domain import SummaryCategory, SummaryItem


class SummaryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_items(self, starts_at: datetime, ends_at: datetime) -> list[SummaryItem]:
        start = _utc(starts_at)
        end = _utc(ends_at)
        with self.database.session() as session:
            module_by_task = _module_by_task(session.scalars(select(ModuleModel)).all())
            items = [
                *self._run_items(session, start, end, module_by_task),
                *self._failed_work_items(session, start, end),
                *self._attention_items(session, start, end),
                *self._comparison_items(session, start, end),
                *self._code_shop_items(session, start, end),
            ]
        return sorted(
            items,
            key=lambda item: (
                item.occurred_at,
                item.category.value,
                item.source_type,
                item.source_id,
            ),
            reverse=True,
        )

    @staticmethod
    def _run_items(
        session: object,
        starts_at: datetime,
        ends_at: datetime,
        module_by_task: dict[str, str],
    ) -> list[SummaryItem]:
        models = session.scalars(
            select(RunModel).where(
                RunModel.finished_at.is_not(None),
                RunModel.finished_at >= starts_at,
                RunModel.finished_at < ends_at,
                RunModel.status.in_(("succeeded", "partial", "failed", "missed")),
            )
        ).all()
        items: list[SummaryItem] = []
        for model in models:
            if model.status == "succeeded":
                category = SummaryCategory.COMPLETED
            elif model.status == "partial":
                category = SummaryCategory.DEGRADED
            else:
                category = SummaryCategory.FAILED
            items.append(
                SummaryItem(
                    category=category,
                    source_type="run",
                    source_id=model.id,
                    module_id=module_by_task.get(model.task_id),
                    occurred_at=_required_utc(model.finished_at),
                    title=f"Run: {model.task_id}",
                    summary=model.result_summary or f"Run ended {model.status}.",
                    detail={
                        "task_id": model.task_id,
                        "status": model.status,
                        "error_code": model.error_code,
                        "session_id": model.session_id,
                    },
                )
            )
        return items

    @staticmethod
    def _failed_work_items(
        session: object,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[SummaryItem]:
        models = session.scalars(
            select(WorkRequestModel).where(
                WorkRequestModel.status == "failed",
                WorkRequestModel.completed_at.is_not(None),
                WorkRequestModel.completed_at >= starts_at,
                WorkRequestModel.completed_at < ends_at,
            )
        ).all()
        return [
            SummaryItem(
                category=SummaryCategory.FAILED,
                source_type="work_request",
                source_id=model.id,
                module_id=model.module_id,
                occurred_at=_required_utc(model.completed_at),
                title=f"Work request failed: {model.task_id}",
                summary=model.error_code or "Durable work request failed.",
                detail={
                    "task_id": model.task_id,
                    "run_id": model.run_id,
                    "work_class": model.work_class,
                    "error_code": model.error_code,
                    "attempt_count": model.attempt_count,
                },
            )
            for model in models
        ]

    @staticmethod
    def _attention_items(
        session: object,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[SummaryItem]:
        models = session.scalars(
            select(AttentionItemModel).where(
                AttentionItemModel.state == AttentionState.OPEN.value,
                AttentionItemModel.created_at >= starts_at,
                AttentionItemModel.created_at < ends_at,
            )
        ).all()
        items: list[SummaryItem] = []
        for model in models:
            category = (
                SummaryCategory.REVIEW
                if model.kind == AttentionKind.REVIEW.value
                else SummaryCategory.BLOCKED
            )
            items.append(
                SummaryItem(
                    category=category,
                    source_type="attention_item",
                    source_id=model.id,
                    module_id=model.module_id,
                    occurred_at=_required_utc(model.created_at),
                    title=model.title,
                    summary=model.summary,
                    detail={
                        "kind": model.kind,
                        "state": model.state,
                        "source_type": model.source_type,
                        "source_id": model.source_id,
                        "dependency_keys": list(model.dependency_keys or []),
                    },
                )
            )
        return items

    @staticmethod
    def _comparison_items(
        session: object,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[SummaryItem]:
        rows = session.execute(
            select(BenchmarkResultModel, BenchmarkCorpusModel)
            .join(
                BenchmarkCorpusModel,
                BenchmarkCorpusModel.id == BenchmarkResultModel.corpus_id,
            )
            .where(
                BenchmarkResultModel.created_at >= starts_at,
                BenchmarkResultModel.created_at < ends_at,
            )
        ).all()
        return [
            SummaryItem(
                category=SummaryCategory.COMPARISON,
                source_type="model_lab_result",
                source_id=result.id,
                module_id=corpus.module_id,
                occurred_at=_required_utc(result.created_at),
                title=f"Model Lab: {corpus.task_id}",
                summary=f"{result.provider}/{result.model}: {result.status}",
                detail={
                    "task_id": corpus.task_id,
                    "corpus_id": result.corpus_id,
                    "session_id": result.session_id,
                    "schema_valid": result.schema_valid,
                    "duration_ms": result.duration_ms,
                    "error_code": result.error_code,
                },
            )
            for result, corpus in rows
        ]

    @staticmethod
    def _code_shop_items(
        session: object,
        starts_at: datetime,
        ends_at: datetime,
    ) -> list[SummaryItem]:
        rows = session.execute(
            select(CodeShopAttemptModel, CodeShopTaskModel)
            .join(CodeShopTaskModel, CodeShopTaskModel.id == CodeShopAttemptModel.task_id)
            .where(
                CodeShopAttemptModel.finished_at.is_not(None),
                CodeShopAttemptModel.finished_at >= starts_at,
                CodeShopAttemptModel.finished_at < ends_at,
                CodeShopAttemptModel.status.in_(("succeeded", "failed")),
            )
        ).all()
        return [
            SummaryItem(
                category=(
                    SummaryCategory.COMPLETED
                    if attempt.status == "succeeded"
                    else SummaryCategory.FAILED
                ),
                source_type="code_shop_attempt",
                source_id=attempt.id,
                module_id="code_shop",
                occurred_at=_required_utc(attempt.finished_at),
                title=task.title,
                summary=(
                    "Code Shop attempt succeeded."
                    if attempt.status == "succeeded"
                    else "Code Shop attempt failed."
                ),
                detail={
                    "task_id": task.id,
                    "repository_id": task.repository_id,
                    "attempt_number": attempt.number,
                    "capability": task.capability,
                    "status": attempt.status,
                },
            )
            for attempt, task in rows
        ]


def _module_by_task(models: list[ModuleModel]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for model in models:
        manifest = dict(model.manifest or {})
        for task in manifest.get("task_types", []):
            if isinstance(task, dict) and task.get("task_id"):
                mapping[str(task["task_id"])] = model.module_id
    return mapping


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("summary window timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _required_utc(value: datetime | None) -> datetime:
    if value is None:
        raise ValueError("summary evidence timestamp is missing")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
