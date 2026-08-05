"""Validated module and task registry."""

from __future__ import annotations

import builtins
from collections.abc import Iterable

from nerve_center import __version__
from nerve_center.domain.module import ModuleManifest
from nerve_center.domain.task import TaskPlugin


class TaskRegistry:
    def __init__(self, core_version: str = __version__) -> None:
        self.core_version = core_version
        self._plugins: dict[str, TaskPlugin] = {}
        self._modules: dict[str, ModuleManifest] = {}
        self._task_modules: dict[str, str] = {}

    def register(self, plugin: TaskPlugin) -> None:
        """Register a manager-owned task that is not supplied by a module."""
        if plugin.plugin_id in self._plugins:
            raise ValueError(f"task plugin {plugin.plugin_id} is already registered")
        self._plugins[plugin.plugin_id] = plugin

    def register_module(
        self,
        manifest: ModuleManifest,
        plugins: Iterable[TaskPlugin],
    ) -> None:
        manifest.validate()
        if not manifest.supports_core(self.core_version):
            raise ValueError(
                f"module {manifest.module_id} {manifest.version} is incompatible with "
                f"core {self.core_version}"
            )
        if manifest.module_id in self._modules:
            raise ValueError(f"module {manifest.module_id} is already registered")
        declared = {task.task_id for task in manifest.task_types}
        supplied = list(plugins)
        supplied_ids = {plugin.plugin_id for plugin in supplied}
        missing = declared - supplied_ids
        undeclared = supplied_ids - declared
        if missing:
            raise ValueError(
                f"module {manifest.module_id} is missing task implementations: "
                f"{', '.join(sorted(missing))}"
            )
        if undeclared:
            raise ValueError(
                f"module {manifest.module_id} does not declare task implementations: "
                f"{', '.join(sorted(undeclared))}"
            )
        for plugin in supplied:
            if plugin.plugin_id in self._plugins:
                raise ValueError(f"task plugin {plugin.plugin_id} is already registered")
        self._modules[manifest.module_id] = manifest
        for plugin in supplied:
            self._plugins[plugin.plugin_id] = plugin
            self._task_modules[plugin.plugin_id] = manifest.module_id

    def get(self, plugin_id: str) -> TaskPlugin:
        try:
            return self._plugins[plugin_id]
        except KeyError as error:
            raise KeyError(f"task plugin {plugin_id} is not registered") from error

    def list(self) -> list[TaskPlugin]:
        return sorted(self._plugins.values(), key=lambda plugin: plugin.display_name.lower())

    def list_modules(self) -> builtins.list[ModuleManifest]:
        return sorted(self._modules.values(), key=lambda module: module.display_name.lower())

    def get_module(self, module_id: str) -> ModuleManifest:
        try:
            return self._modules[module_id]
        except KeyError as error:
            raise KeyError(f"module {module_id} is not registered") from error

    def module_for_task(self, task_id: str) -> ModuleManifest | None:
        module_id = self._task_modules.get(task_id)
        return self._modules.get(module_id) if module_id else None
