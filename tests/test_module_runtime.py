import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from nerve_center.config import Settings
from nerve_center.domain.budget import ResourceBudget, ResourceBudgetTracker
from nerve_center.domain.module_runtime import ModuleRuntimeStatus
from nerve_center.domain.task import TaskContext, TaskResult, TaskStatus
from nerve_center.plugins.job_scout.manifest import job_scout_manifest
from nerve_center.runtime.supervisor import (
    ModuleRuntimeAuthorizationError,
    ModuleSupervisor,
)


class StubBridge:
    async def invoke(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"operation": operation, "payload": payload}


class StubProcess:
    pid = 1234
    returncode: int | None = None

    def __init__(self) -> None:
        self._finished = asyncio.Event()

    async def wait(self) -> int:
        await self._finished.wait()
        return self.returncode or 0

    def terminate(self) -> None:
        self.returncode = 0
        self._finished.set()

    def kill(self) -> None:
        self.returncode = -9
        self._finished.set()


def test_runtime_token_assignment_and_manager_callbacks(tmp_path: Path) -> None:
    asyncio.run(_exercise_runtime(tmp_path))


async def _exercise_runtime(tmp_path: Path) -> None:
    process = StubProcess()
    launch: dict[str, Any] = {}

    async def process_factory(*command: str, **kwargs: Any) -> StubProcess:
        launch["command"] = command
        launch["environment"] = kwargs["env"]
        return process

    supervisor = ModuleSupervisor(Settings(data_dir=tmp_path), process_factory)
    manifest = job_scout_manifest()
    supervisor.register(manifest, StubBridge())
    checkpoints: list[dict[str, Any]] = []
    tracker = ResourceBudgetTracker(ResourceBudget(max_requests=2))
    context = TaskContext(
        run_id="run-1",
        started_at=datetime.now(UTC),
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        cancellation_requested=lambda: False,
        save_checkpoint=lambda value: checkpoints.append(dict(value)),
        resources=tracker,
    )

    execution = asyncio.create_task(
        supervisor.execute("job_scout", "job_scout.discovery", context, priority=25)
    )
    await asyncio.sleep(0)
    token = launch["environment"]["NERVE_CENTER_RUNTIME_TOKEN"]

    with pytest.raises(ModuleRuntimeAuthorizationError):
        supervisor.next_assignment("job_scout", "wrong-token")
    assignment = supervisor.next_assignment("job_scout", token)
    assert assignment is not None
    assert assignment["priority"] == 25
    assert assignment["data_directory"] == str(tmp_path / "modules" / "job_scout")
    assert supervisor.next_assignment("job_scout", token) is None

    supervisor.checkpoint("job_scout", token, "run-1", {"completed": 1})
    usage = supervisor.consume_resource("job_scout", token, "run-1", "requests", 1)
    operation = await supervisor.invoke(
        "job_scout", token, "run-1", "probe", {"value": 7}
    )
    supervisor.heartbeat(
        "job_scout",
        token,
        status=ModuleRuntimeStatus.WORKING,
        activity="Testing",
        deterministic_backlog=3,
    )
    supervisor.complete(
        "job_scout",
        token,
        "run-1",
        result=_result(),
    )

    result = await execution
    assert result.status == TaskStatus.SUCCEEDED
    assert checkpoints == [{"completed": 1}]
    assert usage == {"requests": 1, "llm_calls": 0}
    assert operation == {"operation": "probe", "payload": {"value": 7}}
    assert supervisor.report("job_scout").work_items_processed == 1
    await supervisor.shutdown()


def _result() -> TaskResult:
    return TaskResult(TaskStatus.SUCCEEDED, "complete", {"count": 1})
