"""Durable manager-owned Attention and Review queue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from nerve_center.attention.domain import (
    AttentionEvent,
    AttentionItem,
    AttentionKind,
    AttentionState,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import Base


class AttentionItemModel(Base):
    __tablename__ = "core_attention_items"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "idempotency_key",
            name="uq_attention_module_idempotency",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    module_id: Mapped[str] = mapped_column(String(100), index=True)
    source_type: Mapped[str] = mapped_column(String(100), index=True)
    source_id: Mapped[str] = mapped_column(String(100), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    allowed_dispositions: Mapped[list[str]] = mapped_column(JSON, default=list)
    validation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    downstream_meaning: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    dependency_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(16), index=True)
    resolution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AttentionEventModel(Base):
    __tablename__ = "core_attention_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("core_attention_items.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AttentionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def submit(
        self,
        *,
        kind: AttentionKind,
        module_id: str,
        source_type: str,
        source_id: str,
        idempotency_key: str,
        title: str,
        summary: str,
        context: dict[str, Any],
        allowed_dispositions: tuple[str, ...],
        validation: dict[str, Any],
        downstream_meaning: dict[str, Any],
        dependency_keys: tuple[str, ...],
    ) -> tuple[AttentionItem, bool]:
        now = datetime.now(UTC)
        with self.database.session() as session:
            existing = session.scalar(
                select(AttentionItemModel).where(
                    AttentionItemModel.module_id == module_id,
                    AttentionItemModel.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return _item(existing), False
            model = AttentionItemModel(
                id=str(uuid4()),
                kind=kind.value,
                module_id=module_id,
                source_type=source_type,
                source_id=source_id,
                idempotency_key=idempotency_key,
                title=title,
                summary=summary,
                context=dict(context),
                allowed_dispositions=list(allowed_dispositions),
                validation=dict(validation),
                downstream_meaning=dict(downstream_meaning),
                dependency_keys=list(dependency_keys),
                state=AttentionState.OPEN.value,
                resolution={},
                created_at=now,
                updated_at=now,
                resolved_at=None,
            )
            session.add(model)
            session.flush()
            session.add(
                AttentionEventModel(
                    item_id=model.id,
                    event_type="created",
                    detail={"module_id": module_id, "source_type": source_type},
                    created_at=now,
                )
            )
            session.flush()
            return _item(model), True

    def get(self, item_id: str) -> AttentionItem:
        with self.database.session() as session:
            model = session.get(AttentionItemModel, item_id)
            if model is None:
                raise KeyError(f"attention item {item_id!r} was not found")
            return _item(model)

    def list(
        self,
        *,
        state: AttentionState | None = None,
        kind: AttentionKind | None = None,
        module_id: str | None = None,
        dependency_key: str | None = None,
        limit: int = 200,
    ) -> list[AttentionItem]:
        statement = select(AttentionItemModel)
        if state is not None:
            statement = statement.where(AttentionItemModel.state == state.value)
        if kind is not None:
            statement = statement.where(AttentionItemModel.kind == kind.value)
        if module_id is not None:
            statement = statement.where(AttentionItemModel.module_id == module_id)
        statement = statement.order_by(AttentionItemModel.created_at.desc()).limit(limit)
        with self.database.session() as session:
            items = [_item(model) for model in session.scalars(statement).all()]
        if dependency_key is not None:
            items = [
                item for item in items if dependency_key in item.dependency_keys
            ]
        return items

    def transition(
        self,
        item_id: str,
        state: AttentionState,
        *,
        resolution: dict[str, Any],
        actor: str,
    ) -> AttentionItem:
        if state == AttentionState.OPEN:
            raise ValueError("attention items cannot transition back to open")
        now = datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(AttentionItemModel, item_id)
            if model is None:
                raise KeyError(f"attention item {item_id!r} was not found")
            if model.state != AttentionState.OPEN.value:
                if model.state == state.value and dict(model.resolution or {}) == resolution:
                    return _item(model)
                raise ValueError(f"attention item is already {model.state}")
            model.state = state.value
            model.resolution = dict(resolution)
            model.updated_at = now
            model.resolved_at = now
            session.add(
                AttentionEventModel(
                    item_id=item_id,
                    event_type=state.value,
                    detail={"actor": actor, "resolution": dict(resolution)},
                    created_at=now,
                )
            )
            session.flush()
            return _item(model)

    def history(self, item_id: str) -> list[AttentionEvent]:
        self.get(item_id)
        with self.database.session() as session:
            models = session.scalars(
                select(AttentionEventModel)
                .where(AttentionEventModel.item_id == item_id)
                .order_by(AttentionEventModel.id.asc())
            ).all()
            return [_event(model) for model in models]


def _item(model: AttentionItemModel) -> AttentionItem:
    return AttentionItem(
        id=model.id,
        kind=AttentionKind(model.kind),
        module_id=model.module_id,
        source_type=model.source_type,
        source_id=model.source_id,
        idempotency_key=model.idempotency_key,
        title=model.title,
        summary=model.summary,
        context=dict(model.context or {}),
        allowed_dispositions=tuple(model.allowed_dispositions or []),
        validation=dict(model.validation or {}),
        downstream_meaning=dict(model.downstream_meaning or {}),
        dependency_keys=tuple(model.dependency_keys or []),
        state=AttentionState(model.state),
        resolution=dict(model.resolution or {}),
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
        resolved_at=_utc(model.resolved_at) if model.resolved_at else None,
    )


def _event(model: AttentionEventModel) -> AttentionEvent:
    return AttentionEvent(
        id=model.id,
        item_id=model.item_id,
        event_type=model.event_type,
        detail=dict(model.detail or {}),
        created_at=_utc(model.created_at),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
