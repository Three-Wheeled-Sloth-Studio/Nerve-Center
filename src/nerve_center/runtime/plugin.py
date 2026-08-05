"""Task-plugin adapter for supervised module workers."""

from nerve_center.domain.module import ModuleManifest
from nerve_center.domain.task import TaskContext, TaskResult
from nerve_center.runtime.supervisor import ModuleSupervisor


class ModuleProcessTaskPlugin:
    def __init__(
        self,
        supervisor: ModuleSupervisor,
        manifest: ModuleManifest,
        task_id: str,
        display_name: str,
    ) -> None:
        self.supervisor = supervisor
        self.manifest = manifest
        self.plugin_id = task_id
        self.display_name = display_name

    async def run(self, context: TaskContext) -> TaskResult:
        return await self.supervisor.execute(
            self.manifest.module_id,
            self.plugin_id,
            context,
            priority=context.module_priority,
        )
