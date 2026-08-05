"""Built-in Job Scout module declaration."""

from nerve_center import __version__
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


def job_scout_manifest() -> ModuleManifest:
    return ModuleManifest(
        manifest_version=MODULE_MANIFEST_VERSION,
        module_id="job_scout",
        display_name="Job Scout",
        description="Discovers, evaluates, and tracks public job opportunities.",
        version=__version__,
        compatibility=ModuleCompatibility(
            module_api_version=MODULE_API_VERSION,
            minimum_core_version=__version__,
            maximum_tested_core_version=__version__,
            data_schema_version=1,
        ),
        launch=ModuleLaunchDefinition(
            runtime="in_process_adapter",
            entrypoint="nerve_center.discovery.plugin:JobDiscoveryTaskPlugin",
        ),
        storage_namespace="job_scout",
        permissions=(
            ModulePermission(
                kind=ModulePermissionKind.PUBLIC_NETWORK_READ,
                scopes=("configured_source_domains",),
                rationale="Retrieve configured public job pages, feeds, and APIs.",
            ),
            ModulePermission(
                kind=ModulePermissionKind.BROWSER_AUTOMATION,
                scopes=("public_read_only",),
                rationale="Read public search results when direct sources are insufficient.",
                required=False,
            ),
            ModulePermission(
                kind=ModulePermissionKind.ASSIGNED_STORAGE_WRITE,
                scopes=("job_scout",),
                rationale="Persist module-owned records and generated local artifacts.",
            ),
        ),
        task_types=(
            ModuleTaskDeclaration(
                task_id="job_scout.discovery",
                display_name="Discover opportunities",
                work_classes=("network", "deterministic"),
            ),
        ),
        ui_contributions=(
            ModuleUiContribution(slot="module_dashboard", renderer_key="job_scout.review"),
            ModuleUiContribution(slot="module_configuration", renderer_key="job_scout.settings"),
            ModuleUiContribution(slot="module_records", renderer_key="job_scout.applications"),
        ),
        configuration_schema={
            "type": "object",
            "properties": {
                "source_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                }
            },
            "additionalProperties": False,
        },
    )
