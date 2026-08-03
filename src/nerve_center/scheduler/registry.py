"""Task-plugin registry."""

from __future__ import annotations

from nerve_center.domain.task import TaskPlugin


class TaskRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, TaskPlugin] = {}

    def register(self, plugin: TaskPlugin) -> None:
        if plugin.plugin_id in self._plugins:
            raise ValueError(f"task plugin {plugin.plugin_id} is already registered")
        self._plugins[plugin.plugin_id] = plugin

    def get(self, plugin_id: str) -> TaskPlugin:
        try:
            return self._plugins[plugin_id]
        except KeyError as error:
            raise KeyError(f"task plugin {plugin_id} is not registered") from error

    def list(self) -> list[TaskPlugin]:
        return sorted(self._plugins.values(), key=lambda plugin: plugin.display_name.lower())
