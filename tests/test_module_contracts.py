from dataclasses import replace

import pytest

from nerve_center.domain.module import (
    MODULE_API_VERSION,
    MODULE_MANIFEST_VERSION,
    ModuleCompatibility,
    ModuleLaunchDefinition,
    ModuleManifest,
    ModulePermission,
    ModulePermissionKind,
    ModuleTaskDeclaration,
    ModuleUiContribution,
)


def manifest() -> ModuleManifest:
    return ModuleManifest(
        manifest_version=MODULE_MANIFEST_VERSION,
        module_id="example_module",
        display_name="Example Module",
        description="Exercises the module contract.",
        version="1.2.3",
        compatibility=ModuleCompatibility(
            module_api_version=MODULE_API_VERSION,
            minimum_core_version="0.6.0",
            maximum_tested_core_version="0.7.0",
            data_schema_version=1,
        ),
        launch=ModuleLaunchDefinition(
            runtime="managed_python",
            entrypoint="example_module.runtime:main",
        ),
        storage_namespace="example_module",
        permissions=(
            ModulePermission(
                kind=ModulePermissionKind.PUBLIC_NETWORK_READ,
                scopes=("configured_source_domains",),
                rationale="Read configured public sources.",
            ),
        ),
        task_types=(
            ModuleTaskDeclaration(
                task_id="example_module.scan",
                display_name="Scan",
                work_classes=("network",),
            ),
        ),
        ui_contributions=(
            ModuleUiContribution(slot="module_dashboard", renderer_key="example.dashboard"),
        ),
        configuration_schema={"type": "object", "additionalProperties": False},
    )


def test_manifest_round_trips_through_persisted_payload() -> None:
    original = manifest()

    restored = ModuleManifest.from_dict(original.to_dict())

    assert restored == original
    assert restored.supports_core("0.6.0")
    assert restored.supports_core("0.7.0")
    assert not restored.supports_core("0.8.0")


def test_manifest_rejects_task_outside_module_namespace() -> None:
    with pytest.raises(ValueError, match="module namespace"):
        replace(
            manifest(),
            task_types=(
                ModuleTaskDeclaration(
                    task_id="other.scan",
                    display_name="Scan",
                    work_classes=("network",),
                ),
            ),
        )


def test_manifest_rejects_unsupported_contract_version() -> None:
    with pytest.raises(ValueError, match="manifest version"):
        replace(manifest(), manifest_version=MODULE_MANIFEST_VERSION + 1)
