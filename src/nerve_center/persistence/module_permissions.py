"""Durable manager-owned module permission review state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from nerve_center.domain.module import ModuleManifest, ModulePermissionKind
from nerve_center.module_permissions.domain import (
    NormalizedPermission,
    PermissionClass,
    PermissionDecision,
    PermissionReview,
    PermissionReviewState,
    normalize_permissions,
    permission_fingerprint,
    review_state,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import Base


class ModulePermissionReviewModel(Base):
    __tablename__ = "core_module_permission_reviews"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "module_version",
            "permission_fingerprint",
            name="uq_module_permission_review_identity",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    module_id: Mapped[str] = mapped_column(String(100), index=True)
    module_version: Mapped[str] = mapped_column(String(100), index=True)
    permission_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    permissions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    decisions: Mapped[dict[str, dict[str, Any]]] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModulePermissionReviewRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_review(self, manifest: ModuleManifest) -> PermissionReview | None:
        permissions = normalize_permissions(manifest)
        if not permissions:
            return None
        fingerprint = permission_fingerprint(permissions)
        with self.database.session() as session:
            existing = session.scalar(
                select(ModulePermissionReviewModel).where(
                    ModulePermissionReviewModel.module_id == manifest.module_id,
                    ModulePermissionReviewModel.module_version == manifest.version,
                    ModulePermissionReviewModel.permission_fingerprint == fingerprint,
                )
            )
            if existing is not None:
                return _review(existing)

            inherited = session.scalar(
                select(ModulePermissionReviewModel)
                .where(
                    ModulePermissionReviewModel.module_id == manifest.module_id,
                    ModulePermissionReviewModel.permission_fingerprint == fingerprint,
                )
                .order_by(ModulePermissionReviewModel.updated_at.desc())
                .limit(1)
            )
            decisions: dict[str, dict[str, Any]] = {}
            if inherited is not None:
                for key, decision in dict(inherited.decisions or {}).items():
                    decisions[key] = {
                        **dict(decision),
                        "provenance": {
                            "source": "identical_permission_carry_forward",
                            "inherited_review_id": inherited.id,
                            "original_provenance": dict(
                                decision.get("provenance", {})
                            ),
                        },
                    }
            model = self._create_model(
                manifest,
                permissions,
                fingerprint,
                decisions,
            )
            session.add(model)
            session.flush()
            return _review(model)

    def bootstrap_legacy(self, manifest: ModuleManifest) -> PermissionReview | None:
        permissions = normalize_permissions(manifest)
        if not permissions:
            return None
        fingerprint = permission_fingerprint(permissions)
        now = datetime.now(UTC)
        with self.database.session() as session:
            existing = session.scalar(
                select(ModulePermissionReviewModel).where(
                    ModulePermissionReviewModel.module_id == manifest.module_id
                )
            )
            if existing is not None:
                return _review(existing)
            decisions = {}
            for permission in permissions:
                if permission.permission_class == PermissionClass.PROHIBITED_EXTERNAL_ACTION:
                    continue
                decisions[permission.key] = {
                    "decision": PermissionDecision.APPROVED.value,
                    "actor": "system",
                    "provenance": {
                        "source": "schema14_migration",
                        "reason": "preexisting installed permission request",
                    },
                    "decided_at": now.isoformat(),
                }
            model = self._create_model(
                manifest,
                permissions,
                fingerprint,
                decisions,
                now=now,
            )
            session.add(model)
            session.flush()
            return _review(model)

    def list(
        self,
        *,
        module_id: str | None = None,
        state: PermissionReviewState | None = None,
        limit: int = 200,
    ) -> list[PermissionReview]:
        statement = select(ModulePermissionReviewModel)
        if module_id is not None:
            statement = statement.where(ModulePermissionReviewModel.module_id == module_id)
        if state is not None:
            statement = statement.where(ModulePermissionReviewModel.state == state.value)
        statement = statement.order_by(
            ModulePermissionReviewModel.updated_at.desc()
        ).limit(limit)
        with self.database.session() as session:
            return [_review(item) for item in session.scalars(statement).all()]

    def get(self, review_id: str) -> PermissionReview:
        with self.database.session() as session:
            model = session.get(ModulePermissionReviewModel, review_id)
            if model is None:
                raise KeyError(f"module permission review {review_id!r} was not found")
            return _review(model)

    def latest_for_manifest(self, manifest: ModuleManifest) -> PermissionReview | None:
        permissions = normalize_permissions(manifest)
        if not permissions:
            return None
        fingerprint = permission_fingerprint(permissions)
        with self.database.session() as session:
            model = session.scalar(
                select(ModulePermissionReviewModel)
                .where(
                    ModulePermissionReviewModel.module_id == manifest.module_id,
                    ModulePermissionReviewModel.module_version == manifest.version,
                    ModulePermissionReviewModel.permission_fingerprint == fingerprint,
                )
                .order_by(ModulePermissionReviewModel.updated_at.desc())
                .limit(1)
            )
            return _review(model) if model is not None else None

    def decide(
        self,
        review_id: str,
        permission_key: str,
        decision: PermissionDecision,
        *,
        actor: str,
        provenance: dict[str, Any],
    ) -> PermissionReview:
        now = datetime.now(UTC)
        with self.database.session() as session:
            model = session.get(ModulePermissionReviewModel, review_id)
            if model is None:
                raise KeyError(f"module permission review {review_id!r} was not found")
            permissions = _permissions(model.permissions)
            permission = next(
                (item for item in permissions if item.key == permission_key),
                None,
            )
            if permission is None:
                raise ValueError("permission is not declared by this review")
            if (
                decision == PermissionDecision.APPROVED
                and permission.permission_class
                == PermissionClass.PROHIBITED_EXTERNAL_ACTION
            ):
                raise ValueError(
                    "prohibited external-action permissions cannot be approved"
                )
            decisions = {
                key: dict(value) for key, value in dict(model.decisions or {}).items()
            }
            decisions[permission_key] = {
                "decision": decision.value,
                "actor": actor.strip(),
                "provenance": dict(provenance),
                "decided_at": now.isoformat(),
            }
            state, _ = review_state(permissions, decisions)
            model.decisions = decisions
            model.state = state.value
            model.updated_at = now
            session.flush()
            return _review(model)

    def operationally_allowed(self, manifest: ModuleManifest) -> bool:
        review = self.ensure_review(manifest)
        return review is None or review.operationally_allowed

    @staticmethod
    def _create_model(
        manifest: ModuleManifest,
        permissions: tuple[NormalizedPermission, ...],
        fingerprint: str,
        decisions: dict[str, dict[str, Any]],
        *,
        now: datetime | None = None,
    ) -> ModulePermissionReviewModel:
        current = now or datetime.now(UTC)
        state, _ = review_state(permissions, decisions)
        return ModulePermissionReviewModel(
            id=str(uuid4()),
            module_id=manifest.module_id,
            module_version=manifest.version,
            permission_fingerprint=fingerprint,
            permissions=[item.to_dict() for item in permissions],
            decisions=decisions,
            state=state.value,
            created_at=current,
            updated_at=current,
        )


def _review(model: ModulePermissionReviewModel) -> PermissionReview:
    permissions = _permissions(model.permissions)
    decisions = {
        key: dict(value) for key, value in dict(model.decisions or {}).items()
    }
    state, operationally_allowed = review_state(permissions, decisions)
    return PermissionReview(
        id=model.id,
        module_id=model.module_id,
        module_version=model.module_version,
        permission_fingerprint=model.permission_fingerprint,
        permissions=permissions,
        decisions=decisions,
        state=state,
        operationally_allowed=operationally_allowed,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _permissions(
    values: list[dict[str, Any]] | None,
) -> tuple[NormalizedPermission, ...]:
    return tuple(
        NormalizedPermission(
            key=str(item["key"]),
            kind=ModulePermissionKind(item["kind"]),
            scopes=tuple(item.get("scopes", ())),
            rationale=str(item.get("rationale", "")),
            required=bool(item.get("required", True)),
            permission_class=PermissionClass(item["permission_class"]),
        )
        for item in (values or [])
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
