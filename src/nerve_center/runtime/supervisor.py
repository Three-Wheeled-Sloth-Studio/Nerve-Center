"""Manager-owned module process supervision and scoped runtime sessions."""

from __future__ import annotations

import asyncio
import os
import secrets
import subprocess
import sys
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from nerve_center.config import Settings
from nerve_center.domain.module import ModuleManifest
from nerve_center.domain.module_runtime import (
    MODULE_RUNTIME_API_VERSION,
    ModuleRunAssignment,
    ModuleRuntimeReport,
    ModuleRuntimeStatus,
)
from nerve_center.domain.task import TaskContext, TaskResult, TaskStatus
from nerve_center.domain.work_queue import (
    QueueStatusSnapshot,
    WorkClass,
    WorkRequestSnapshot,
    WorkRequestSpec,
    WorkResultSnapshot,
)


class ModuleOperationBridge(Protocol):
    async def invoke(self, operation: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...


class ModuleWorkQueue(Protocol):
    def submit(self, spec: WorkRequestSpec) -> WorkRequestSnapshot: ...

    def status(self, module_id: str | None = None) -> QueueStatusSnapshot: ...

    def deliver_results(self, module_id: str) -> list[WorkResultSnapshot]: ...

    def acknowledge(self, result_id: str, module_id: str) -> WorkResultSnapshot: ...


@dataclass(slots=True)
class _PendingRun:
    assignment: ModuleRunAssignment
    context: TaskContext
    completion: asyncio.Future[TaskResult]
    claimed: bool = False


@dataclass(slots=True)
class _ModuleSession:
    manifest: ModuleManifest
    bridge: ModuleOperationBridge
    token: str
    report: ModuleRuntimeReport
    process: asyncio.subprocess.Process | None = None
    process_log: Any = None
    process_monitor: asyncio.Task[None] | None = None
    pending: _PendingRun | None = None
    stop_requested: bool = False
    lock: asyncio.Lock | None = None


class ModuleRuntimeAuthorizationError(PermissionError):
    pass


class ModuleRuntimeConflictError(RuntimeError):
    pass


class ModuleSupervisor:
    def __init__(
        self,
        settings: Settings,
        process_factory: Callable[..., Awaitable[asyncio.subprocess.Process]] | None = None,
        session_control: Callable[[str], Mapping[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self._process_factory = process_factory or asyncio.create_subprocess_exec
        self._sessions: dict[str, _ModuleSession] = {}
        self._session_control = session_control
        self._work_queue: ModuleWorkQueue | None = None

    def register(self, manifest: ModuleManifest, bridge: ModuleOperationBridge) -> None:
        if manifest.module_id in self._sessions:
            raise ValueError(f"duplicate module runtime {manifest.module_id!r}")
        self._sessions[manifest.module_id] = _ModuleSession(
            manifest=manifest,
            bridge=bridge,
            token=secrets.token_urlsafe(32),
            report=ModuleRuntimeReport(
                module_id=manifest.module_id,
                status=ModuleRuntimeStatus.STOPPED,
                activity="Not running",
            ),
        )

    def set_session_control_resolver(
        self, resolver: Callable[[str], Mapping[str, Any]]
    ) -> None:
        self._session_control = resolver

    def set_work_queue(self, work_queue: ModuleWorkQueue) -> None:
        self._work_queue = work_queue

    def report(self, module_id: str) -> ModuleRuntimeReport:
        session = self._session(module_id)
        report = session.report
        if (
            session.process is not None
            and session.process.returncode is None
            and report.last_heartbeat_at is not None
            and (datetime.now(UTC) - report.last_heartbeat_at).total_seconds()
            > self.settings.module_heartbeat_timeout_seconds
        ):
            session.report = self._updated_report(
                session,
                ModuleRuntimeStatus.DEGRADED,
                "Module heartbeat is overdue",
                reason="heartbeat timeout",
            )
        if self._work_queue is not None:
            queue = self._work_queue.status(module_id)
            session.report = self._updated_report(
                session,
                session.report.status,
                session.report.activity,
                pending_llm_requests=queue.queued + queue.claimed,
                estimated_next_request_wait_seconds=(
                    queue.estimated_next_request_wait_seconds
                ),
                estimated_queue_clear_seconds=queue.estimated_queue_clear_seconds,
                queue_pressure=queue.pressure,
            )
        return session.report

    def authorize(self, module_id: str, token: str) -> None:
        if not secrets.compare_digest(self._session(module_id).token, token):
            raise ModuleRuntimeAuthorizationError("invalid module runtime token")

    async def execute(
        self,
        module_id: str,
        task_id: str,
        context: TaskContext,
        *,
        priority: int,
    ) -> TaskResult:
        session = self._session(module_id)
        if session.lock is None:
            session.lock = asyncio.Lock()
        async with session.lock:
            await self._ensure_started(session)
            loop = asyncio.get_running_loop()
            assignment = ModuleRunAssignment(
                runtime_api_version=MODULE_RUNTIME_API_VERSION,
                module_id=module_id,
                module_version=session.manifest.version,
                run_id=context.run_id,
                session_id=context.session_id,
                task_id=task_id,
                deadline=context.deadline,
                priority=priority,
                queue_limits=self._queue_limits(module_id),
                resource_policy={
                    "max_requests": context.resources.budget.max_requests,
                    "max_llm_calls": context.resources.budget.max_llm_calls,
                    "max_parallel_work": context.resources.budget.max_parallel_work,
                },
                data_directory=str(
                    self.settings.module_data_dir(session.manifest.storage_namespace)
                ),
                admission_phase=str(
                    self._session_policy(context.session_id)["admission_phase"]
                ),
                configuration=dict(context.configuration),
                checkpoint=dict(context.checkpoint),
            )
            session.pending = _PendingRun(
                assignment=assignment,
                context=context,
                completion=loop.create_future(),
            )
            session.report = self._updated_report(
                session,
                ModuleRuntimeStatus.IDLE,
                "Run queued for module worker",
                deterministic_backlog=1,
                queue_pressure=0.01,
            )
            try:
                return await session.pending.completion
            finally:
                session.pending = None

    def next_assignment(self, module_id: str, token: str) -> dict[str, Any] | None:
        self.authorize(module_id, token)
        pending = self._session(module_id).pending
        if pending is None or pending.claimed:
            return None
        pending.claimed = True
        return pending.assignment.to_dict()

    def control(self, module_id: str, token: str, run_id: str) -> dict[str, Any]:
        self.authorize(module_id, token)
        session = self._session(module_id)
        pending = self._pending(session, run_id)
        return {
            "cancel_requested": pending.context.cancellation_requested(),
            "shutdown_requested": session.stop_requested,
            "deadline": pending.assignment.deadline,
            **self._session_policy(pending.assignment.session_id),
        }

    def module_control(self, module_id: str, token: str) -> dict[str, bool]:
        self.authorize(module_id, token)
        return {"shutdown_requested": self._session(module_id).stop_requested}

    def checkpoint(
        self,
        module_id: str,
        token: str,
        run_id: str,
        value: Mapping[str, Any],
    ) -> None:
        self.authorize(module_id, token)
        self._pending(self._session(module_id), run_id).context.save_checkpoint(value)

    def consume_resource(
        self,
        module_id: str,
        token: str,
        run_id: str,
        resource: str,
        count: int,
    ) -> dict[str, int]:
        self.authorize(module_id, token)
        tracker = self._pending(self._session(module_id), run_id).context.resources
        if resource == "requests":
            usage = tracker.consume_request(count)
        elif resource == "llm_calls":
            usage = tracker.consume_llm_call(count)
        else:
            raise ValueError(f"unsupported resource {resource!r}")
        return {"requests": usage.requests, "llm_calls": usage.llm_calls}

    async def invoke(
        self,
        module_id: str,
        token: str,
        run_id: str,
        operation: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.authorize(module_id, token)
        session = self._session(module_id)
        self._pending(session, run_id)
        return await session.bridge.invoke(operation, payload)

    def submit_work(
        self,
        module_id: str,
        token: str,
        run_id: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.authorize(module_id, token)
        pending = self._pending(self._session(module_id), run_id)
        if self._work_queue is None:
            raise ModuleRuntimeConflictError("durable work queue is unavailable")
        snapshot = self._work_queue.submit(
            WorkRequestSpec(
                module_id=module_id,
                run_id=run_id,
                session_id=pending.assignment.session_id,
                task_id=str(request["task_id"]),
                work_class=WorkClass(request["work_class"]),
                payload=dict(request["payload"]),
                provenance=dict(request.get("provenance", {})),
                output_contract=dict(request.get("output_contract", {})),
                requirements=dict(request.get("requirements", {})),
                idempotency_key=str(request["idempotency_key"]),
                module_priority=pending.assignment.priority,
                task_priority=int(request.get("task_priority", 50)),
                max_retries=int(request.get("max_retries", 2)),
            )
        )
        return asdict(snapshot)

    def deliver_results(self, module_id: str, token: str) -> list[dict[str, Any]]:
        self.authorize(module_id, token)
        if self._work_queue is None:
            raise ModuleRuntimeConflictError("durable work queue is unavailable")
        return [asdict(item) for item in self._work_queue.deliver_results(module_id)]

    def acknowledge_result(
        self, module_id: str, token: str, result_id: str
    ) -> dict[str, Any]:
        self.authorize(module_id, token)
        if self._work_queue is None:
            raise ModuleRuntimeConflictError("durable work queue is unavailable")
        return asdict(self._work_queue.acknowledge(result_id, module_id))

    def complete(
        self,
        module_id: str,
        token: str,
        run_id: str,
        result: TaskResult,
    ) -> None:
        self.authorize(module_id, token)
        session = self._session(module_id)
        pending = self._pending(session, run_id)
        if not pending.completion.done():
            pending.completion.set_result(result)
        session.report = self._updated_report(
            session,
            ModuleRuntimeStatus.IDLE,
            result.summary,
            deterministic_backlog=0,
            work_items_processed=session.report.work_items_processed + 1,
        )

    def heartbeat(
        self,
        module_id: str,
        token: str,
        *,
        status: ModuleRuntimeStatus,
        activity: str,
        deterministic_backlog: int = 0,
        pending_llm_requests: int = 0,
        queue_pressure: float = 0.0,
        reason: str | None = None,
    ) -> ModuleRuntimeReport:
        self.authorize(module_id, token)
        session = self._session(module_id)
        session.report = self._updated_report(
            session,
            status,
            activity,
            touch_heartbeat=True,
            deterministic_backlog=deterministic_backlog,
            pending_llm_requests=pending_llm_requests,
            queue_pressure=queue_pressure,
            reason=reason,
        )
        return session.report

    async def stop(self, module_id: str, timeout_seconds: float = 5.0) -> None:
        session = self._session(module_id)
        process = session.process
        if process is None:
            return
        session.stop_requested = True
        session.report = self._updated_report(
            session, ModuleRuntimeStatus.STOPPING, "Stopping module worker"
        )
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout_seconds)
        except TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except TimeoutError:
                process.kill()
                await process.wait()
        finally:
            if session.process_monitor is not None:
                session.process_monitor.cancel()
                await asyncio.gather(session.process_monitor, return_exceptions=True)
                session.process_monitor = None
            session.process = None
            session.stop_requested = False
            if session.process_log is not None:
                session.process_log.close()
                session.process_log = None
            if session.pending is not None and not session.pending.completion.done():
                session.pending.completion.set_result(
                    TaskResult(
                        TaskStatus.CANCELLED,
                        "Module worker stopped before the assigned run completed.",
                    )
                )
            session.report = self._updated_report(
                session, ModuleRuntimeStatus.STOPPED, "Module worker stopped"
            )

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.stop(module_id) for module_id in self._sessions))

    async def _ensure_started(self, session: _ModuleSession) -> None:
        if session.process is not None and session.process.returncode is None:
            return
        if session.process_monitor is not None:
            await asyncio.gather(session.process_monitor, return_exceptions=True)
            session.process_monitor = None
        if session.process_log is not None:
            session.process_log.close()
            session.process_log = None
        session.process = None
        data_dir = self.settings.module_data_dir(session.manifest.storage_namespace)
        data_dir.mkdir(parents=True, exist_ok=True)
        log_path = data_dir / "runtime.log"
        session.process_log = log_path.open("ab")
        command = self._command(session.manifest)
        environment = os.environ.copy()
        environment.update(
            {
                "NERVE_CENTER_RUNTIME_ENDPOINT": self.settings.manager_endpoint,
                "NERVE_CENTER_RUNTIME_TOKEN": session.token,
                "NERVE_CENTER_MODULE_ID": session.manifest.module_id,
                "NERVE_CENTER_MODULE_DATA_DIR": str(data_dir),
            }
        )
        session.report = self._updated_report(
            session, ModuleRuntimeStatus.STARTING, "Launching module worker"
        )
        session.process = await self._process_factory(
            *command,
            env=environment,
            cwd=str(data_dir),
            stdout=session.process_log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        session.report = self._updated_report(
            session,
            ModuleRuntimeStatus.STARTING,
            "Waiting for module heartbeat",
            process_id=session.process.pid,
        )
        session.process_monitor = asyncio.create_task(self._watch_process(session))

    async def _watch_process(self, session: _ModuleSession) -> None:
        process = session.process
        if process is None:
            return
        return_code = await process.wait()
        if session.stop_requested:
            return
        session.report = self._updated_report(
            session,
            ModuleRuntimeStatus.FAILED,
            "Module worker exited unexpectedly",
            reason=f"process exited with code {return_code}",
        )
        if session.pending is not None and not session.pending.completion.done():
            session.pending.completion.set_exception(
                RuntimeError(
                    f"module {session.manifest.module_id} exited with code {return_code}"
                )
            )

    @staticmethod
    def _command(manifest: ModuleManifest) -> list[str]:
        if manifest.launch.runtime != "managed_python":
            raise ValueError(f"unsupported module runtime {manifest.launch.runtime!r}")
        if getattr(sys, "frozen", False):
            return [sys.executable, "--module-worker", manifest.launch.entrypoint]
        return [sys.executable, "-m", manifest.launch.entrypoint, *manifest.launch.arguments]

    @staticmethod
    def _pending(session: _ModuleSession, run_id: str) -> _PendingRun:
        if session.pending is None or session.pending.assignment.run_id != run_id:
            raise ModuleRuntimeConflictError(f"run {run_id} is not assigned to this module")
        return session.pending

    def _session(self, module_id: str) -> _ModuleSession:
        try:
            return self._sessions[module_id]
        except KeyError as error:
            raise KeyError(f"module runtime {module_id!r} is not registered") from error

    def _session_policy(self, session_id: str | None) -> Mapping[str, Any]:
        if session_id is None or self._session_control is None:
            return {
                "admission_phase": "open",
                "remaining_seconds": None,
                "estimated_queue_clear_seconds": 0.0,
                "estimated_next_request_wait_seconds": 0.0,
                "accept_new_llm_work": True,
            }
        return self._session_control(session_id)

    def _queue_limits(self, module_id: str) -> dict[str, int]:
        if self._work_queue is None:
            return {"soft": 25, "hard": 100}
        status = self._work_queue.status(module_id)
        return {"soft": status.soft_limit, "hard": status.hard_limit}

    @staticmethod
    def _updated_report(
        session: _ModuleSession,
        status: ModuleRuntimeStatus,
        activity: str,
        touch_heartbeat: bool = False,
        **changes: Any,
    ) -> ModuleRuntimeReport:
        current = session.report
        values = current.to_dict()
        values.update(changes)
        values.update({"status": status, "activity": activity})
        if touch_heartbeat:
            values["last_heartbeat_at"] = datetime.now(UTC)
        return ModuleRuntimeReport(**values)
