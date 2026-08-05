"""Versioned contracts for independently packaged Nerve Center modules."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Self

MODULE_MANIFEST_VERSION = 1
MODULE_API_VERSION = 1
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_-]*)*$")
_SEMANTIC_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")


class ModuleLifecycleState(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    NOT_INSTALLED = "not_installed"


class ModulePermissionKind(StrEnum):
    PUBLIC_NETWORK_READ = "public_network_read"
    AUTHENTICATED_READ = "authenticated_read"
    ASSIGNED_STORAGE_WRITE = "assigned_storage_write"
    EXTERNAL_PATH_READ = "external_path_read"
    EXTERNAL_PATH_WRITE = "external_path_write"
    BROWSER_AUTOMATION = "browser_automation"
    CLIPBOARD = "clipboard"
    NOTIFICATIONS = "notifications"
    PROCESS = "process"
    DEVICE = "device"
    CREDENTIAL_REFERENCE = "credential_reference"
    EXTERNAL_DRAFT = "external_draft"
    CLOUD_ELIGIBLE_DATA = "cloud_eligible_data"


@dataclass(frozen=True, slots=True)
class ModulePermission:
    kind: ModulePermissionKind
    scopes: tuple[str, ...] = ()
    rationale: str = ""
    required: bool = True


@dataclass(frozen=True, slots=True)
class ModuleCompatibility:
    module_api_version: int
    minimum_core_version: str
    maximum_tested_core_version: str
    data_schema_version: int


@dataclass(frozen=True, slots=True)
class ModuleLaunchDefinition:
    runtime: str
    entrypoint: str
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleTaskDeclaration:
    task_id: str
    display_name: str
    work_classes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModuleUiContribution:
    slot: str
    renderer_key: str


@dataclass(frozen=True, slots=True)
class ModuleManifest:
    manifest_version: int
    module_id: str
    display_name: str
    description: str
    version: str
    compatibility: ModuleCompatibility
    launch: ModuleLaunchDefinition
    storage_namespace: str
    permissions: tuple[ModulePermission, ...]
    task_types: tuple[ModuleTaskDeclaration, ...]
    ui_contributions: tuple[ModuleUiContribution, ...] = ()
    configuration_schema: dict[str, Any] = field(default_factory=dict)
    session_entry_task_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.manifest_version != MODULE_MANIFEST_VERSION:
            raise ValueError(
                f"unsupported module manifest version {self.manifest_version}; "
                f"expected {MODULE_MANIFEST_VERSION}"
            )
        if self.compatibility.module_api_version != MODULE_API_VERSION:
            raise ValueError(
                f"unsupported module API version {self.compatibility.module_api_version}; "
                f"expected {MODULE_API_VERSION}"
            )
        if not _IDENTIFIER.fullmatch(self.module_id):
            raise ValueError(f"invalid module identifier {self.module_id!r}")
        if not _IDENTIFIER.fullmatch(self.storage_namespace):
            raise ValueError(f"invalid module storage namespace {self.storage_namespace!r}")
        _parse_version(self.version)
        _parse_version(self.compatibility.minimum_core_version)
        _parse_version(self.compatibility.maximum_tested_core_version)
        if self.compatibility.data_schema_version < 1:
            raise ValueError("module data schema version must be positive")
        if not self.display_name.strip() or not self.description.strip():
            raise ValueError("module display name and description are required")
        task_ids: set[str] = set()
        for task in self.task_types:
            if not task.task_id.startswith(f"{self.module_id}."):
                raise ValueError(
                    f"task {task.task_id!r} is outside module namespace {self.module_id!r}"
                )
            if task.task_id in task_ids:
                raise ValueError(f"duplicate module task declaration {task.task_id!r}")
            if not task.work_classes:
                raise ValueError(f"module task {task.task_id!r} must declare work classes")
            task_ids.add(task.task_id)
        if self.session_entry_task_id is not None and self.session_entry_task_id not in task_ids:
            raise ValueError("session entry task must be declared by the module")

    def supports_core(self, core_version: str) -> bool:
        current = _parse_version(core_version)
        return (
            _parse_version(self.compatibility.minimum_core_version)
            <= current
            <= _parse_version(self.compatibility.maximum_tested_core_version)
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        compatibility = ModuleCompatibility(**value["compatibility"])
        launch_value = value["launch"]
        launch = ModuleLaunchDefinition(
            runtime=launch_value["runtime"],
            entrypoint=launch_value["entrypoint"],
            arguments=tuple(launch_value.get("arguments", ())),
        )
        permissions = tuple(
            ModulePermission(
                kind=ModulePermissionKind(item["kind"]),
                scopes=tuple(item.get("scopes", ())),
                rationale=item.get("rationale", ""),
                required=item.get("required", True),
            )
            for item in value.get("permissions", ())
        )
        tasks = tuple(
            ModuleTaskDeclaration(
                task_id=item["task_id"],
                display_name=item["display_name"],
                work_classes=tuple(item["work_classes"]),
            )
            for item in value.get("task_types", ())
        )
        ui = tuple(ModuleUiContribution(**item) for item in value.get("ui_contributions", ()))
        return cls(
            manifest_version=value["manifest_version"],
            module_id=value["module_id"],
            display_name=value["display_name"],
            description=value["description"],
            version=value["version"],
            compatibility=compatibility,
            launch=launch,
            storage_namespace=value["storage_namespace"],
            permissions=permissions,
            task_types=tasks,
            ui_contributions=ui,
            configuration_schema=dict(value.get("configuration_schema", {})),
            session_entry_task_id=value.get("session_entry_task_id"),
        )


@dataclass(frozen=True, slots=True)
class InstalledModule:
    manifest: ModuleManifest
    lifecycle_state: ModuleLifecycleState
    saved_priority: int


def _parse_version(value: str) -> tuple[int, int, int]:
    match = _SEMANTIC_VERSION.fullmatch(value)
    if not match:
        raise ValueError(f"invalid semantic version {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]
