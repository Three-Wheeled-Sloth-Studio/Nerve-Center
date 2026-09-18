from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.attention.domain import AttentionKind, AttentionState
from nerve_center.code_shop.domain import EngineeringCapability, GitHubRepositoryIdentity
from nerve_center.config import Settings
from nerve_center.domain.run import RunStatus
from nerve_center.domain.run_window import DurationRunWindow
from nerve_center.domain.work_queue import WorkClass, WorkRequestSpec, WorkRequestStatus
from nerve_center.persistence.attention import AttentionRepository
from nerve_center.persistence.code_shop import CodeShopRepository
from nerve_center.persistence.database import Database
from nerve_center.persistence.model_lab import ModelLabRepository
from nerve_center.persistence.runs import RunRepository
from nerve_center.persistence.work_queue import WorkQueueRepository


def _window(now: datetime) -> tuple[datetime, datetime]:
    return now - timedelta(minutes=5), now + timedelta(minutes=5)


def _terminal_run(
    repository: RunRepository,
    *,
    task_id: str,
    status: RunStatus,
    now: datetime,
    summary: str,
) -> str:
    created = repository.create(
        task_id,
        DurationRunWindow(timedelta(minutes=5)),
        now=now,
    )
    repository.transition(
        created.id,
        RunStatus.RUNNING,
        now=now + timedelta(seconds=1),
        starts_at=now + timedelta(seconds=1),
    )
    terminal = repository.transition(
        created.id,
        status,
        now=now + timedelta(seconds=2),
        result_summary=summary,
        error_code="TEST_ERROR" if status == RunStatus.FAILED else None,
    )
    return terminal.id


def _query(client: TestClient, start: datetime, end: datetime) -> dict:
    response = client.get(
        "/api/v1/summary",
        params={"starts_at": start.isoformat(), "ends_at": end.isoformat()},
    )
    assert response.status_code == 200
    return response.json()


def test_summary_empty_window_and_invalid_window_are_deterministic(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))
    start = datetime(2020, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=1)

    with TestClient(app) as client:
        first = _query(client, start, end)
        second = _query(client, start, end)
        invalid = client.get(
            "/api/v1/summary",
            params={"starts_at": end.isoformat(), "ends_at": start.isoformat()},
        )

    assert first == second
    assert first["items"] == []
    assert first["counts"] == {
        "completed": 0,
        "blocked": 0,
        "failed": 0,
        "degraded": 0,
        "comparison": 0,
        "review": 0,
    }
    assert invalid.status_code == 422


def test_summary_aggregates_only_durable_attributable_window_evidence(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path)
    database = Database(settings)
    database.initialize()
    now = datetime.now(UTC)
    start, end = _window(now)

    runs = RunRepository(database)
    succeeded_run = _terminal_run(
        runs,
        task_id="synthetic",
        status=RunStatus.SUCCEEDED,
        now=now,
        summary="Synthetic run completed.",
    )
    partial_run = _terminal_run(
        runs,
        task_id="synthetic",
        status=RunStatus.PARTIAL,
        now=now + timedelta(seconds=5),
        summary="Synthetic run completed partially.",
    )
    failed_run = _terminal_run(
        runs,
        task_id="synthetic",
        status=RunStatus.FAILED,
        now=now + timedelta(seconds=10),
        summary="Synthetic run failed.",
    )
    outside_run = _terminal_run(
        runs,
        task_id="synthetic",
        status=RunStatus.SUCCEEDED,
        now=now - timedelta(days=2),
        summary="Outside window.",
    )

    queue = WorkQueueRepository(database)
    work, created = queue.submit(
        WorkRequestSpec(
            module_id="job_scout",
            run_id=failed_run,
            task_id="job_scout.discover",
            work_class=WorkClass.NETWORK,
            payload={},
            idempotency_key="summary-failed-work",
            max_retries=0,
        ),
        now=now,
    )
    assert created is True
    attempt = queue.claim_next("summary-test", now=now + timedelta(seconds=1))
    assert attempt is not None
    failed_work = queue.fail(
        attempt.id,
        "NETWORK_FAILED",
        now=now + timedelta(seconds=2),
    )
    assert failed_work.status == WorkRequestStatus.FAILED

    attention = AttentionRepository(database)
    blocked, _ = attention.submit(
        kind=AttentionKind.ATTENTION,
        module_id="job_scout",
        source_type="test_blocker",
        source_id="blocker-1",
        idempotency_key="summary-blocker",
        title="Job Scout needs attention",
        summary="A durable branch is blocked.",
        context={},
        allowed_dispositions=("continue", "stop"),
        validation={},
        downstream_meaning={},
        dependency_keys=("job_scout:test:branch",),
    )
    review, _ = attention.submit(
        kind=AttentionKind.REVIEW,
        module_id="job_scout",
        source_type="test_review",
        source_id="review-1",
        idempotency_key="summary-review",
        title="Review retained opportunities",
        summary="Human review is pending.",
        context={},
        allowed_dispositions=("accept", "revise"),
        validation={},
        downstream_meaning={},
        dependency_keys=("job_scout:test:review",),
    )

    model_lab = ModelLabRepository(database)
    corpus, _ = model_lab.add_corpus(
        fingerprint="summary-corpus",
        module_id="job_scout",
        task_id="job_scout.discover",
        run_id=succeeded_run,
        work_request_id=work.id,
        contract_version="summary-v1",
        system_prompt="safe system",
        user_prompt="safe user",
        output_schema={"type": "object"},
        requirements={},
        expected_output={},
        production_provider=None,
        production_model=None,
        production_call_id=None,
        created_at=now,
    )
    lab_session = model_lab.start_session(3600, 5, now=now)
    benchmark = model_lab.record_result(
        corpus_id=corpus.id,
        session_id=lab_session.id,
        provider="ollama",
        model="test-model",
        status="succeeded",
        schema_valid=True,
        duration_ms=25,
        output={},
        error_code=None,
        provider_call_id=None,
        now=now + timedelta(seconds=3),
    )

    code_shop = CodeShopRepository(database)
    code_shop.upsert_project(
        GitHubRepositoryIdentity(
            repository_id="summary-repo",
            full_name="Three-Wheeled-Sloth-Studio/Nerve-Center",
            visibility="public",
            default_branch="dev",
        )
    )
    task = code_shop.create_task(
        "summary-repo",
        title="Summary Code Shop task",
        capability=EngineeringCapability.CODE_IMPLEMENTATION,
        source_backlog={"issue": 62},
    )
    code_attempt = code_shop.record_attempt(
        task.id,
        status="succeeded",
        approach="bounded implementation",
        context_inputs={},
        manager_provenance={},
        touched_files=(),
        command_summaries=(),
        resources={},
        outcome={"status": "green"},
    )

    app = create_app(settings)
    with TestClient(app) as client:
        snapshot = _query(client, start, end)

    items = snapshot["items"]
    by_source = {(item["source_type"], item["source_id"]): item for item in items}
    categories = {item["category"] for item in items}

    assert {
        "completed",
        "blocked",
        "failed",
        "degraded",
        "comparison",
        "review",
    }.issubset(categories)
    assert ("run", succeeded_run) in by_source
    assert ("run", partial_run) in by_source
    assert ("run", failed_run) in by_source
    assert ("run", outside_run) not in by_source
    assert ("work_request", work.id) in by_source
    assert ("attention_item", blocked.id) in by_source
    assert ("attention_item", review.id) in by_source
    assert ("model_lab_result", benchmark.id) in by_source
    assert ("code_shop_attempt", code_attempt.id) in by_source
    assert by_source[("work_request", work.id)]["module_id"] == "job_scout"
    assert by_source[("model_lab_result", benchmark.id)]["module_id"] == "job_scout"
    assert by_source[("code_shop_attempt", code_attempt.id)]["module_id"] == "code_shop"


def test_summary_survives_restart_and_has_no_mutation_side_effects(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path)
    database = Database(settings)
    database.initialize()
    now = datetime.now(UTC)
    start, end = _window(now)

    runs = RunRepository(database)
    run_id = _terminal_run(
        runs,
        task_id="synthetic",
        status=RunStatus.SUCCEEDED,
        now=now,
        summary="Durable completed work.",
    )
    attention = AttentionRepository(database)
    blocker, _ = attention.submit(
        kind=AttentionKind.ATTENTION,
        module_id="job_scout",
        source_type="restart_test",
        source_id="restart-1",
        idempotency_key="restart-summary-blocker",
        title="Persisted blocker",
        summary="This blocker must survive restart.",
        context={},
        allowed_dispositions=("continue",),
        validation={},
        downstream_meaning={},
        dependency_keys=("restart:test",),
    )

    before = attention.get(blocker.id)
    first_app = create_app(settings)
    with TestClient(first_app) as client:
        first = _query(client, start, end)
        dependency_before = client.get(
            "/api/v1/attention/dependencies/restart:test/blocked"
        ).json()

    after_first = attention.get(blocker.id)
    second_app = create_app(settings)
    with TestClient(second_app) as client:
        second = _query(client, start, end)
        dependency_after = client.get(
            "/api/v1/attention/dependencies/restart:test/blocked"
        ).json()

    assert first == second
    assert ("run", run_id) in {
        (item["source_type"], item["source_id"]) for item in second["items"]
    }
    assert before.state == AttentionState.OPEN
    assert after_first.state == AttentionState.OPEN
    assert attention.get(blocker.id).state == AttentionState.OPEN
    assert dependency_before["blocked"] is True
    assert dependency_after["blocked"] is True
