"""Module permission normalization and review contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from nerve_center.domain.module import ModuleManifest, ModulePermission, ModulePermissionKind


class PermissionReviewState(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class PermissionDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"


class PermissionClass(StrEnum):
    PUBLIC_READ = "public_read"
    AUTHENTICATED_READ = "authenticated_read"
    LOCAL_WRITE = "local_write"
    EXTERNAL_DRAFT = "external_draft"
    PROHIBITED_EXTERNAL_ACTION = "prohibited_external_action"


@dataclass(frozen=True, slots=True)
class NormalizedPermission:
    key: str
    kind: ModulePermissionKind
    scopes: tuple[str, ...]
    rationale: str
    required: bool
    permission_class: PermissionClass

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind.value,
            "scopes": list(self.scopes),
            "rationale": self.rationale,
            "required": self.required,
            "permission_class": self.permission_class.value,
        }


@dataclass(frozen=True, slots=True)
class PermissionReview:
    id: str
    module_id: str
    module_version: str
    permission_fingerprint: str
    permissions: tuple[NormalizedPermission, ...]
    decisions: dict[str, dict[str, Any]]
    state: PermissionReviewState
    operationally_allowed: bool
    created_at: datetime
    updated_at: datetime


def normalize_permissions(
    manifest: ModuleManifest,
) -> tuple[NormalizedPermission, ...]:
    normalized: dict[str, NormalizedPermission] = {}
    for permission in manifest.permissions:
        canonical = _canonical_permission(permission)
        key = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        normalized[key] = NormalizedPermission(
            key=key,
            kind=permission.kind,
            scopes=tuple(canonical["scopes"]),
            rationale=str(canonical["rationale"]),
            required=bool(canonical["required"]),
            permission_class=permission_class(permission),
        )
    return tuple(
        sorted(
            normalized.values(),
            key=lambda item: (item.kind.value, item.scopes, item.required, item.key),
        )
    )


def permission_fingerprint(permissions: tuple[NormalizedPermission, ...]) -> str:
    payload = [
        {
            "kind": item.kind.value,
            "scopes": list(item.scopes),
            "rationale": item.rationale,
            "required": item.required,
            "permission_class": item.permission_class.value,
        }
        for item in permissions
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def permission_class(permission: ModulePermission) -> PermissionClass:
    kind = permission.kind
    if kind == ModulePermissionKind.PUBLIC_NETWORK_READ:
        return PermissionClass.PUBLIC_READ
    if kind == ModulePermissionKind.BROWSER_AUTOMATION:
        scopes = {scope.strip() for scope in permission.scopes if scope.strip()}
        if scopes and scopes.issubset({"public_read_only"}):
            return PermissionClass.PUBLIC_READ
        return PermissionClass.PROHIBITED_EXTERNAL_ACTION
    if kind in {
        ModulePermissionKind.AUTHENTICATED_READ,
        ModulePermissionKind.CREDENTIAL_REFERENCE,
    }:
        return PermissionClass.AUTHENTICATED_READ
    if kind in {
        ModulePermissionKind.ASSIGNED_STORAGE_WRITE,
        ModulePermissionKind.EXTERNAL_PATH_READ,
        ModulePermissionKind.EXTERNAL_PATH_WRITE,
        ModulePermissionKind.CLIPBOARD,
        ModulePermissionKind.CLOUD_ELIGIBLE_DATA,
    }:
        return PermissionClass.LOCAL_WRITE
    if kind == ModulePermissionKind.EXTERNAL_DRAFT:
        return PermissionClass.EXTERNAL_DRAFT
    return PermissionClass.PROHIBITED_EXTERNAL_ACTION


def review_state(
    permissions: tuple[NormalizedPermission, ...],
    decisions: dict[str, dict[str, Any]],
) -> tuple[PermissionReviewState, bool]:
    required = [item for item in permissions if item.required]
    for item in required:
        decision = decisions.get(item.key, {}).get("decision")
        if decision == PermissionDecision.DENIED.value:
            return PermissionReviewState.DENIED, False
    operationally_allowed = all(
        decisions.get(item.key, {}).get("decision") == PermissionDecision.APPROVED.value
        for item in required
    )
    if not operationally_allowed:
        return PermissionReviewState.PENDING, False
    if all(item.key in decisions for item in permissions):
        return PermissionReviewState.APPROVED, True
    return PermissionReviewState.PENDING, True


def _canonical_permission(permission: ModulePermission) -> dict[str, Any]:
    return {
        "kind": permission.kind.value,
        "scopes": sorted({scope.strip() for scope in permission.scopes if scope.strip()}),
        "rationale": permission.rationale.strip(),
        "required": bool(permission.required),
    }
