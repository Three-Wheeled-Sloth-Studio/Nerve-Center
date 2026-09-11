import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from nerve_center.config import Settings
from nerve_center.domain.budget import ResourceBudget, ResourceBudgetTracker
from nerve_center.domain.module import ModuleTaskDeclaration
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


def test_module_runtime_backoff_checkpoint_does_not_block_another_module(
    tmp_path: Path,
) -> None:
    asyncio.run(_exercise_independent_modules(tmp_path))


async def _exercise_independent_modules(tmp_path: Path) -> None:
    processes: dict[str, StubProcess] = {}
    environments: dict[str, dict[str, str]] = {}

    async def process_factory(*_command: str, **kwargs: Any) -> StubProcess:
        environment = kwargs["env"]
        module_id = environment["NERVE_CENTER_MODULE_ID"]
        process = StubProcess()
        processes[module_id] = process
        environments[module_id] = environment
        return process

    settings = Settings(data_dir=tmp_path)
    supervisor = ModuleSupervisor(settings, process_factory)
    manifest = job_scout_manifest()
    other_manifest = replace(
        manifest,
        module_id="other_module",
        display_name="Other Module",
        storage_namespace="other_module",
        task_types=(
            ModuleTaskDeclaration(
                task_id="other_module.work",
                display_name="Other work",
                work_classes=("deterministic",),
            ),
        ),
        session_entry_task_id="other_module.work",
    )
    supervisor.register(manifest, StubBridge())
    supervisor.register(other_manifest, StubBridge())
    database = Database(settings)
    database.initialize()
    runs = RunRepository(database)

    def context(task_id: str) -> TaskContext:
        run = runs.create(task_id, DurationRunWindow(timedelta(minutes=1)))
        return TaskContext(
            run_id=run.id,
            started_at=datetime.now(UTC),
            deadline=datetime.now(UTC) + timedelta(minutes=1),
            cancellation_requested=lambda: False,
            save_checkpoint=lambda _value: None,
            resources=ResourceBudgetTracker(ResourceBudget()),
        )

    job_context = context("job_scout.discovery")
    other_context = context("other_module.work")
    job_execution = asyncio.create_task(
        supervisor.execute(
            "job_scout", "job_scout.discovery", job_context, priority=25
        )
    )
    other_execution = asyncio.create_task(
        supervisor.execute(
            "other_module", "other_module.work", other_context, priority=25
        )
    )
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    job_token = environments["job_scout"]["NERVE_CENTER_RUNTIME_TOKEN"]
    other_token = environments["other_module"]["NERVE_CENTER_RUNTIME_TOKEN"]
    assert supervisor.next_assignment("job_scout", job_token) is not None
    assert supervisor.next_assignment("other_module", other_token) is not None
    supervisor.checkpoint(
        "job_scout",
        job_token,
        job_context.run_id,
        {"phase": "backoff", "backoff_scope": "discovery"},
    )

    supervisor.complete(
        "other_module", other_token, other_context.run_id, result=_result()
    )
    assert (await asyncio.wait_for(other_execution, timeout=1)).status == (
        TaskStatus.SUCCEEDED
    )
    assert not job_execution.done()

    supervisor.complete("job_scout", job_token, job_context.run_id, result=_result())
    await job_execution
    await supervisor.shutdown()


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
