import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from nerve_center.config import Settings
from nerve_center.domain.budget import ResourceBudget, ResourceBudgetTracker
from nerve_center.domain.module_runtime import ModuleRuntimeStatus
from nerve_center.domain.run_window import DurationRunWindow
from nerve_center.domain.task import TaskContext, TaskResult, TaskStatus
from nerve_center.persistence.database import Database
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.work_queue import WorkQueueRepository
from nerve_center.plugins.job_scout.manifest import job_scout_manifest
from nerve_center.runtime.supervisor import (
    ModuleRuntimeAuthorizationError,
    ModuleSupervisor,
)
from nerve_center.scheduler.work_queue import WorkQueueService


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
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    run = RunRepository(database).create(
        "job_scout.discovery", DurationRunWindow(timedelta(minutes=1))
    )
    work_queue = WorkQueueService(WorkQueueRepository(database))
    supervisor.set_work_queue(work_queue)
    manifest = job_scout_manifest()
    supervisor.register(manifest, StubBridge())
    checkpoints: list[dict[str, Any]] = []
    tracker = ResourceBudgetTracker(ResourceBudget(max_requests=2))
    context = TaskContext(
        run_id=run.id,
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

    supervisor.checkpoint("job_scout", token, run.id, {"completed": 1})
    usage = supervisor.consume_resource("job_scout", token, run.id, "requests", 1)
    operation = await supervisor.invoke(
        "job_scout", token, run.id, "probe", {"value": 7}
    )
    queued = supervisor.submit_work(
        "job_scout",
        token,
        run.id,
        {
            "task_id": "job_scout.evaluate_fit",
            "work_class": "llm",
            "payload": {"job_id": "job-1"},
            "output_contract": {"type": "object"},
            "idempotency_key": "job-1-fit",
        },
    )
    attempt = work_queue.claim_next("provider-worker")
    assert attempt is not None
    completed = work_queue.complete(attempt.id, {"fit": "strong"})
    delivered = supervisor.deliver_results("job_scout", token)
    acknowledged = supervisor.acknowledge_result("job_scout", token, completed.id)
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
        run.id,
        result=_result(),
    )

    result = await execution
    assert result.status == TaskStatus.SUCCEEDED
    assert checkpoints == [{"completed": 1}]
    assert usage == {"requests": 1, "llm_calls": 0}
    assert operation == {"operation": "probe", "payload": {"value": 7}}
    assert queued["status"] == "queued"
    assert delivered[0]["payload"] == {"fit": "strong"}
    assert acknowledged["acknowledged_at"] is not None
    assert supervisor.report("job_scout").work_items_processed == 1
    await supervisor.shutdown()


def _result() -> TaskResult:
    return TaskResult(TaskStatus.SUCCEEDED, "complete", {"count": 1})
