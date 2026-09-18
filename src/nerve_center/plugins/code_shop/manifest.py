"""Built-in Code Shop module declaration."""

from nerve_center import __version__
from nerve_center.domain.module import (
    MODULE_API_VERSION,
    MODULE_MANIFEST_VERSION,
    ModuleCompatibility,
    ModuleLaunchDefinition,
    ModuleManifest,
    ModuleTaskDeclaration,
    ModuleUiContribution,
)


def code_shop_manifest() -> ModuleManifest:
    return ModuleManifest(
        manifest_version=MODULE_MANIFEST_VERSION,
        module_id="code_shop",
        display_name="Code Shop",
        description=(
            "Coordinates bounded software-engineering work while manager-owned services "
            "retain repository, authority, provider, and privileged execution control."
        ),
        version=__version__,
        compatibility=ModuleCompatibility(
            module_api_version=MODULE_API_VERSION,
            minimum_core_version=__version__,
            maximum_tested_core_version=__version__,
            data_schema_version=1,
        ),
        launch=ModuleLaunchDefinition(
            runtime="managed_python",
            entrypoint="nerve_center.plugins.code_shop.worker",
        ),
        storage_namespace="code_shop",
        permissions=(),
        task_types=(
            ModuleTaskDeclaration(
                task_id="code_shop.orchestrate",
                display_name="Orchestrate engineering work",
                work_classes=("deterministic",),
            ),
        ),
        ui_contributions=(
            ModuleUiContribution(slot="module_panel", renderer_key="code_shop"),
        ),
        configuration_schema={
            "type": "object",
            "properties": {
                "repository_id": {"type": "string"},
                "title": {"type": "string"},
                "capability": {
                    "type": "string",
                    "enum": [
                        "architecture_planning",
                        "task_decomposition",
                        "code_implementation",
                        "debugging",
                        "code_review",
                        "research",
                    ],
                },
                "source_backlog": {"type": "object"},
            },
            "required": ["repository_id", "title", "capability"],
            "additionalProperties": False,
        },
        session_entry_task_id=None,
    )
