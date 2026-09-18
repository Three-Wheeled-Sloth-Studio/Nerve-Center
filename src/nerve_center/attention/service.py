"""Manager-owned Attention and Review service."""

from __future__ import annotations

from nerve_center.attention.domain import (
    AttentionEvent,
    AttentionItem,
    AttentionKind,
    AttentionState,
)
from nerve_center.persistence.attention import AttentionRepository


class AttentionService:
    def __init__(self, repository: AttentionRepository) -> None:
        self.repository = repository

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
        context: dict[str, object] | None = None,
        allowed_dispositions: tuple[str, ...] = (),
        validation: dict[str, object] | None = None,
        downstream_meaning: dict[str, object] | None = None,
        dependency_keys: tuple[str, ...] = (),
    ) -> tuple[AttentionItem, bool]:
        dispositions = tuple(
            sorted({item.strip() for item in allowed_dispositions if item.strip()})
        )
        dependencies = tuple(
            sorted({item.strip() for item in dependency_keys if item.strip()})
        )
        return self.repository.submit(
            kind=kind,
            module_id=module_id.strip(),
            source_type=source_type.strip(),
            source_id=source_id.strip(),
            idempotency_key=idempotency_key.strip(),
            title=title.strip(),
            summary=summary.strip(),
            context=dict(context or {}),
            allowed_dispositions=dispositions,
            validation=dict(validation or {}),
            downstream_meaning=dict(downstream_meaning or {}),
            dependency_keys=dependencies,
        )

    def get(self, item_id: str) -> AttentionItem:
        return self.repository.get(item_id)

    def list(
        self,
        *,
        state: AttentionState | None = None,
        kind: AttentionKind | None = None,
        module_id: str | None = None,
        dependency_key: str | None = None,
        limit: int = 200,
    ) -> list[AttentionItem]:
        return self.repository.list(
            state=state,
            kind=kind,
            module_id=module_id,
            dependency_key=dependency_key,
            limit=limit,
        )

    def resolve(
        self,
        item_id: str,
        *,
        disposition: str,
        detail: dict[str, object] | None = None,
        actor: str = "user",
    ) -> AttentionItem:
        item = self.repository.get(item_id)
        selected = disposition.strip()
        if item.allowed_dispositions and selected not in item.allowed_dispositions:
            raise ValueError(
                f"disposition {selected!r} is not allowed for attention item {item_id}"
            )
        return self.repository.transition(
            item_id,
            AttentionState.RESOLVED,
            resolution={"disposition": selected, "detail": dict(detail or {})},
            actor=actor,
        )

    def dismiss(
        self,
        item_id: str,
        *,
        reason: str,
        actor: str = "user",
    ) -> AttentionItem:
        return self.repository.transition(
            item_id,
            AttentionState.DISMISSED,
            resolution={"reason": reason.strip()},
            actor=actor,
        )

    def history(self, item_id: str) -> list[AttentionEvent]:
        return self.repository.history(item_id)

    def dependency_blocked(self, dependency_key: str) -> bool:
        return bool(
            self.repository.list(
                state=AttentionState.OPEN,
                dependency_key=dependency_key,
                limit=1_000,
            )
        )
