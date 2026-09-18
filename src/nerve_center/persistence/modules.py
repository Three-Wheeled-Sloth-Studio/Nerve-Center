"""Durable manager-owned installed-module inventory."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select

from nerve_center.domain.module import (
    InstalledModule,
    ModuleLifecycleState,
    ModuleManifest,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import ModuleModel
from nerve_center.persistence.module_permissions import ModulePermissionReviewRepository


class ModuleNotFoundError(KeyError):
    pass


class ModuleRepository:
    def __init__(
        self,
        database: Database,
        permission_reviews: ModulePermissionReviewRepository | None = None,
    ) -> None:
        self.database = database
        self.permission_reviews = permission_reviews or ModulePermissionReviewRepository(
            database
        )

    def synchronize(self, manifests: Iterable[ModuleManifest]) -> list[InstalledModule]:
        available = {manifest.module_id: manifest for manifest in manifests}
        now = datetime.now(UTC)
        with self.database.session() as session:
            existing = {
                model.module_id: model
                for model in session.scalars(select(ModuleModel)).all()
            }
            for module_id, manifest in available.items():
                model = existing.get(module_id)
                if (
                    model is not None
                    and self.database.previous_schema_version is not None
                    and self.database.previous_schema_version < 14
                ):
                    self.permission_reviews.bootstrap_legacy(
                        ModuleManifest.from_dict(dict(model.manifest))
                    )
                review = self.permission_reviews.ensure_review(manifest)
                operationally_allowed = (
                    review is None or review.operationally_allowed
                )
                self.database.settings.module_data_dir(manifest.storage_namespace).mkdir(
                    parents=True,
                    exist_ok=True,
                )
                if model is None:
                    session.add(
                        ModuleModel(
                            module_id=module_id,
                            lifecycle_state=(
                                ModuleLifecycleState.ENABLED
                                if operationally_allowed
                                else ModuleLifecycleState.PAUSED
                            ),
                            saved_priority=10,
                            manifest=manifest.to_dict(),
                            installed_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    model.manifest = manifest.to_dict()
                    if model.lifecycle_state == ModuleLifecycleState.NOT_INSTALLED:
                        model.lifecycle_state = ModuleLifecycleState.PAUSED
                    if not operationally_allowed:
                        model.lifecycle_state = ModuleLifecycleState.PAUSED
                    model.updated_at = now
            for module_id, model in existing.items():
                if module_id not in available:
                    model.lifecycle_state = ModuleLifecycleState.NOT_INSTALLED
                    model.updated_at = now
        return self.list()

    def list(self) -> list[InstalledModule]:
        with self.database.session() as session:
            models = session.scalars(
                select(ModuleModel).order_by(ModuleModel.module_id)
            ).all()
            return [self._snapshot(model) for model in models]

    def get(self, module_id: str) -> InstalledModule:
        with self.database.session() as session:
            model = session.get(ModuleModel, module_id)
            if model is None:
                raise ModuleNotFoundError(f"module {module_id} is not installed")
            return self._snapshot(model)

    def set_lifecycle(
        self,
        module_id: str,
        lifecycle_state: ModuleLifecycleState,
    ) -> InstalledModule:
        if lifecycle_state == ModuleLifecycleState.NOT_INSTALLED:
            raise ValueError("use package removal to mark a module not installed")
        if lifecycle_state == ModuleLifecycleState.ENABLED:
            installed = self.get(module_id)
            if not self.permission_reviews.operationally_allowed(installed.manifest):
                raise ValueError(
                    f"module {module_id} has unapproved required permissions"
                )
        with self.database.session() as session:
            model = session.get(ModuleModel, module_id)
            if model is None or model.lifecycle_state == ModuleLifecycleState.NOT_INSTALLED:
                raise ModuleNotFoundError(f"module {module_id} is not installed")
            model.lifecycle_state = lifecycle_state
            model.updated_at = datetime.now(UTC)
            session.flush()
            return self._snapshot(model)

    @staticmethod
    def _snapshot(model: ModuleModel) -> InstalledModule:
        return InstalledModule(
            manifest=ModuleManifest.from_dict(dict(model.manifest)),
            lifecycle_state=ModuleLifecycleState(model.lifecycle_state),
            saved_priority=model.saved_priority,
        )
