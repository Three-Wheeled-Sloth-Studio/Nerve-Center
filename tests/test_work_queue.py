from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nerve_center.config import Settings
from nerve_center.domain.run_window import DurationRunWindow
from nerve_center.domain.work_queue import (
    QueueLimitExceededError,
    QueueLimits,
    WorkClass,
    WorkRequestSpec,
    WorkRequestStatus,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.work_queue import WorkQueueRepository
from nerve_center.scheduler.work_queue import WorkQueueService


def make_service(
    tmp_path: Path, limits: QueueLimits | None = None
) -> tuple[WorkQueueService, str]:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    run = RunRepository(database).create(
        "job_scout.discovery", DurationRunWindow(timedelta(minutes=5))
    )
    return WorkQueueService(WorkQueueRepository(database), limits=limits), run.id


def spec(run_id: str, key: str = "candidate-1") -> WorkRequestSpec:
    return WorkRequestSpec(
        module_id="job_scout",
        run_id=run_id,
        task_id="job_scout.evaluate_fit",
        work_class=WorkClass.LLM,
        payload={"job_id": "job-1"},
        output_contract={"type": "object"},
        idempotency_key=key,
        module_priority=60,
        task_priority=70,
    )


def test_submit_is_durable_and_idempotent(tmp_path: Path) -> None:
    service, run_id = make_service(tmp_path)

    first = service.submit(spec(run_id))
    duplicate = service.submit(spec(run_id))

    assert duplicate.id == first.id
    assert service.get(first.id).status == WorkRequestStatus.QUEUED
    assert len(service.list_requests()) == 1


def test_result_is_redelivered_until_acknowledged(tmp_path: Path) -> None:
    service, run_id = make_service(tmp_path)
    request = service.submit(spec(run_id))
    attempt = service.claim_next("provider-worker")
    assert attempt is not None
    result = service.complete(attempt.id, {"fit": "strong"})

    first_delivery = service.deliver_results("job_scout")
    second_delivery = service.deliver_results("job_scout")
    assert [item.id for item in first_delivery] == [result.id]
    assert [item.id for item in second_delivery] == [result.id]
    assert second_delivery[0].delivery_count == 2

    service.acknowledge(result.id, "job_scout")
    assert service.deliver_results("job_scout") == []
    assert service.get(request.id).status == WorkRequestStatus.ACKNOWLEDGED


def test_failed_attempt_requeues_and_preserves_attempt_history(tmp_path: Path) -> None:
    service, run_id = make_service(tmp_path)
    request = service.submit(spec(run_id))
    first = service.claim_next("worker-a")
    assert first is not None

    requeued = service.fail(first.id, "provider_timeout", retry_delay_seconds=0)
    second = service.claim_next("worker-b")

    assert requeued.status == WorkRequestStatus.QUEUED
    assert second is not None and second.number == 2
    assert len(service.attempts(request.id)) == 2


def test_model_routing_score_can_outweigh_small_task_priority_gap(tmp_path: Path) -> None:
    service, run_id = make_service(tmp_path)
    higher_priority = service.submit(
        replace(
            spec(run_id, "higher-priority"),
            task_id="task.unproven",
            task_priority=55,
        )
    )
    empirically_suitable = service.submit(
        replace(
            spec(run_id, "empirically-suitable"),
            task_id="task.proven",
            task_priority=50,
        )
    )

    claimed = service.claim_next(
        "provider-worker",
        routing_scores={"task.unproven": 2.0, "task.proven": 9.0},
    )

    assert claimed is not None
    assert claimed.request_id == empirically_suitable.id
    assert claimed.request_id != higher_priority.id


def test_hard_module_limit_rejects_before_acknowledgement(tmp_path: Path) -> None:
    limits = QueueLimits(global_soft=2, global_hard=3, module_soft=1, module_hard=2)
    service, run_id = make_service(tmp_path, limits)
    service.submit(spec(run_id, "one"))
    service.submit(spec(run_id, "two"))

    with pytest.raises(QueueLimitExceededError):
        service.submit(spec(run_id, "three"))

    assert len(service.list_requests()) == 2


def test_order_prefers_module_then_task_priority_then_age(tmp_path: Path) -> None:
    service, run_id = make_service(tmp_path)
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    service.submit(spec(run_id, "older-low"), now=now)
    service.submit(
        WorkRequestSpec(
            module_id="job_scout",
            run_id=run_id,
            task_id="job_scout.evaluate_fit",
            work_class=WorkClass.LLM,
            payload={"job_id": "job-2"},
            output_contract={"type": "object"},
            idempotency_key="newer-high",
            module_priority=80,
            task_priority=90,
        ),
        now=now + timedelta(seconds=1),
    )

    claimed = service.claim_next("worker", now=now + timedelta(seconds=2))

    assert claimed is not None
    assert service.get(claimed.request_id).idempotency_key == "newer-high"


def test_queue_status_reports_pressure_and_wait_estimates(tmp_path: Path) -> None:
    limits = QueueLimits(global_soft=4, global_hard=8, module_soft=2, module_hard=4)
    service, run_id = make_service(tmp_path, limits)
    service.submit(spec(run_id, "one"))
    service.submit(spec(run_id, "two"))

    status = service.status("job_scout")

    assert status.queued == 2
    assert status.pressure == 0.5
    assert status.estimated_next_request_wait_seconds > 0
    assert status.estimated_queue_clear_seconds >= status.estimated_next_request_wait_seconds


def test_claimed_work_is_redelivered_after_manager_restart(tmp_path: Path) -> None:
    service, run_id = make_service(tmp_path)
    request = service.submit(spec(run_id))
    claimed = service.claim_next("worker-before-restart")
    assert claimed is not None

    recovered = service.recover_interrupted()
    redelivered = service.claim_next("worker-after-restart")

    assert [item.id for item in recovered] == [request.id]
    assert redelivered is not None and redelivered.number == 2
    attempts = service.attempts(request.id)
    assert attempts[0].status.value == "interrupted"
    assert attempts[0].error_code == "manager_restart"


def test_concurrent_claims_never_assign_the_same_request(tmp_path: Path) -> None:
    service, run_id = make_service(tmp_path)
    for index in range(8):
        service.submit(spec(run_id, f"request-{index}"))

    with ThreadPoolExecutor(max_workers=4) as executor:
        attempts = list(
            executor.map(lambda index: service.claim_next(f"worker-{index}"), range(8))
        )

    request_ids = [attempt.request_id for attempt in attempts if attempt is not None]
    assert len(request_ids) == 8
    assert len(set(request_ids)) == 8
