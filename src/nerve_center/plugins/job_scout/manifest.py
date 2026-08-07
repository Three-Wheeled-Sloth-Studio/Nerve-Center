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
        description=(
            "Loads career evidence, discovers search terms, scans public sources, "
            "and tracks opportunities."
        ),
        version=__version__,
        compatibility=ModuleCompatibility(
            module_api_version=MODULE_API_VERSION,
            minimum_core_version=__version__,
            maximum_tested_core_version=__version__,
            data_schema_version=4,
        ),
        launch=ModuleLaunchDefinition(
            runtime="managed_python",
            entrypoint="nerve_center.plugins.job_scout.worker",
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
                rationale=(
                    "Persist module-owned configuration, records, and generated local artifacts."
                ),
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
            ModuleUiContribution(slot="module_panel", renderer_key="job_scout"),
        ),
        configuration_schema={
            "type": "object",
            "properties": {
                "resume_document_id": {"type": ["string", "null"]},
                "resume_file_name": {"type": ["string", "null"]},
                "target_titles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "locations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "remote_preference": {
                    "type": "string",
                    "enum": ["any", "remote", "hybrid", "on_site"],
                },
                "source_urls": {
                    "type": "array",
                    "items": {"type": "string", "format": "uri"},
                    "uniqueItems": True,
                },
                "public_job_boards": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "source_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "allowed_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "disallowed_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "manual_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "broad_search_enabled": {"type": "boolean"},
                "scan_interval_minutes": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 10080,
                },
            },
            "additionalProperties": False,
        },
        session_entry_task_id="job_scout.discovery",
    )
