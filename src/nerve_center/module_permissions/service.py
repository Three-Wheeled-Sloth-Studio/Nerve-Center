"""Manager-owned module permission review service."""

from __future__ import annotations

from typing import Any

from nerve_center.module_permissions.domain import (
    PermissionDecision,
    PermissionReview,
    PermissionReviewState,
)
from nerve_center.persistence.module_permissions import ModulePermissionReviewRepository


class ModulePermissionReviewService:
    def __init__(self, repository: ModulePermissionReviewRepository) -> None:
        self.repository = repository

    def list(
        self,
        *,
        module_id: str | None = None,
        state: PermissionReviewState | None = None,
        limit: int = 200,
    ) -> list[PermissionReview]:
        return self.repository.list(module_id=module_id, state=state, limit=limit)

    def get(self, review_id: str) -> PermissionReview:
        return self.repository.get(review_id)

    def approve(
        self,
        review_id: str,
        permission_key: str,
        *,
        actor: str,
        provenance: dict[str, Any],
    ) -> PermissionReview:
        return self.repository.decide(
            review_id,
            permission_key,
            PermissionDecision.APPROVED,
            actor=actor,
            provenance=provenance,
        )

    def deny(
        self,
        review_id: str,
        permission_key: str,
        *,
        actor: str,
        provenance: dict[str, Any],
    ) -> PermissionReview:
        return self.repository.decide(
            review_id,
            permission_key,
            PermissionDecision.DENIED,
            actor=actor,
            provenance=provenance,
        )
