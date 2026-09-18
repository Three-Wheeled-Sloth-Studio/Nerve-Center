from pathlib import Path

from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.code_shop.domain import GitHubRepositoryIdentity
from nerve_center.code_shop.github import StaticGitHubRepositoryConnector
from nerve_center.config import Settings


def _connector() -> StaticGitHubRepositoryConnector:
    return StaticGitHubRepositoryConnector(
        [
            GitHubRepositoryIdentity(
                repository_id="101",
                full_name="Three-Wheeled-Sloth-Studio/Nerve-Center",
                visibility="public",
                default_branch="main",
                metadata={"archived": False},
            )
        ]
    )


def _checkout(
    root: Path,
    *,
    repository: str = "Three-Wheeled-Sloth-Studio/Nerve-Center",
) -> Path:
    path = root / "Nerve-Center"
    (path / ".git").mkdir(parents=True)
    (path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        f"    url = git@github.com:{repository}.git\n"
        "    fetch = +refs/heads/*:refs/remotes/origin/*\n",
        encoding="utf-8",
    )
    return path


def _select_and_enable(client: TestClient) -> dict:
    selected = client.post("/api/v1/modules/code_shop/projects/101/select")
    assert selected.status_code == 201
    enabled = client.patch(
        "/api/v1/modules/code_shop/projects/101",
        json={
            "lifecycle": "enabled",
            "branch_policy": {
                "allowed_branches": ["dev"],
                "protected_branches": ["main"],
            },
        },
    )
    assert enabled.status_code == 200
    return enabled.json()


def _create_task(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/modules/code_shop/tasks",
        json={
            "repository_id": "101",
            "title": "Implement bounded slice",
            "capability": "code_implementation",
            "source_backlog": {"issue": 54},
        },
    )
    assert response.status_code == 201
    return response.json()


def _allow(client: TestClient, action: str) -> None:
    response = client.put(
        f"/api/v1/modules/code_shop/projects/101/authority/{action}",
        json={"policy": "allow", "provenance": {"source": "user"}},
    )
    assert response.status_code == 200


def test_code_shop_is_registered_as_builtin_official_module(tmp_path: Path) -> None:
    app = create_app(
        Settings(data_dir=tmp_path, code_shop_checkout_roots=(tmp_path,)),
        code_shop_connector=_connector(),
    )

    with TestClient(app) as client:
        modules = client.get("/api/v1/modules").json()
        trust = client.get("/api/v1/modules/code_shop/trust")

    ids = {item["manifest"]["module_id"] for item in modules}
    assert {"code_shop", "job_scout"}.issubset(ids)
    code_shop = next(
        item for item in modules if item["manifest"]["module_id"] == "code_shop"
    )
    assert code_shop["manifest"]["storage_namespace"] == "code_shop"
    assert trust.json() == {
        "module_id": "code_shop",
        "official": True,
        "source": "builtin_registry",
    }


def test_project_checkout_and_explicit_allow_admit_only_bounded_execution(
    tmp_path: Path,
) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    checkout = _checkout(approved)
    app = create_app(
        Settings(data_dir=tmp_path / "data", code_shop_checkout_roots=(approved,)),
        code_shop_connector=_connector(),
    )

    with TestClient(app) as client:
        _select_and_enable(client)
        linked = client.put(
            "/api/v1/modules/code_shop/projects/101/checkout",
            json={"path": str(checkout)},
        )
        _allow(client, "checkout_write")
        task = _create_task(client)
        evaluated = client.post(
            "/api/v1/modules/code_shop/execution/evaluate",
            json={
                "task_id": task["id"],
                "repository_id": "101",
                "action": "checkout_write",
                "capability": "repo.write",
                "arguments": {"operation": "write"},
                "expected_outputs": {"files": ["src/example.py"]},
                "resource_paths": ["src/example.py"],
                "idempotency_key": "write-1",
            },
        )
        executed = client.post(
            "/api/v1/modules/code_shop/execution/execute",
            json={
                "task_id": task["id"],
                "repository_id": "101",
                "action": "checkout_write",
                "capability": "repo.write",
                "arguments": {"operation": "write"},
                "expected_outputs": {"files": ["src/example.py"]},
                "resource_paths": ["src/example.py"],
                "idempotency_key": "write-2",
            },
        )

    assert linked.status_code == 200
    assert linked.json()["remote_identity"] == (
        "three-wheeled-sloth-studio/nerve-center"
    )
    assert evaluated.json()["effective_decision"] == "execute"
    assert executed.status_code == 200
    assert executed.json()["result"]["status"] == "simulated"
    assert executed.json()["result"]["output"]["argument_keys"] == ["operation"]


def test_checkout_escape_and_remote_mismatch_are_rejected(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    mismatch = _checkout(approved, repository="Other/Repository")
    outside = _checkout(tmp_path / "outside")
    app = create_app(
        Settings(data_dir=tmp_path / "data", code_shop_checkout_roots=(approved,)),
        code_shop_connector=_connector(),
    )

    with TestClient(app) as client:
        _select_and_enable(client)
        wrong_remote = client.put(
            "/api/v1/modules/code_shop/projects/101/checkout",
            json={"path": str(mismatch)},
        )
        outside_root = client.put(
            "/api/v1/modules/code_shop/projects/101/checkout",
            json={"path": str(outside)},
        )

    assert wrong_remote.status_code == 422
    assert "does not match GitHub repository" in wrong_remote.json()["detail"]
    assert outside_root.status_code == 422
    assert "outside manager-approved roots" in outside_root.json()["detail"]


def test_unlinked_and_observe_only_projects_cannot_mutate(tmp_path: Path) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    checkout = _checkout(approved)
    app = create_app(
        Settings(data_dir=tmp_path / "data", code_shop_checkout_roots=(approved,)),
        code_shop_connector=_connector(),
    )

    with TestClient(app) as client:
        _select_and_enable(client)
        _allow(client, "checkout_write")
        task = _create_task(client)
        base = {
            "task_id": task["id"],
            "repository_id": "101",
            "action": "checkout_write",
            "capability": "repo.write",
            "resource_paths": ["README.md"],
            "idempotency_key": "gate",
        }
        unlinked = client.post(
            "/api/v1/modules/code_shop/execution/evaluate", json=base
        )
        client.put(
            "/api/v1/modules/code_shop/projects/101/checkout",
            json={"path": str(checkout)},
        )
        client.patch(
            "/api/v1/modules/code_shop/projects/101",
            json={"lifecycle": "observe_only"},
        )
        observe_mutation = client.post(
            "/api/v1/modules/code_shop/execution/evaluate", json=base
        )
        _allow(client, "checkout_read")
        observe_read = client.post(
            "/api/v1/modules/code_shop/execution/evaluate",
            json={
                **base,
                "action": "checkout_read",
                "capability": "repo.read",
                "idempotency_key": "read",
            },
        )

    assert unlinked.json()["effective_decision"] == "deny"
    assert "no verified linked checkout" in unlinked.json()["reason"]
    assert observe_mutation.json()["effective_decision"] == "deny"
    assert observe_read.json()["effective_decision"] == "execute"


def test_ask_and_high_risk_actions_enter_attention_and_untrusted_module_is_denied(
    tmp_path: Path,
) -> None:
    approved = tmp_path / "approved"
    approved.mkdir()
    checkout = _checkout(approved)
    app = create_app(
        Settings(data_dir=tmp_path / "data", code_shop_checkout_roots=(approved,)),
        code_shop_connector=_connector(),
    )

    with TestClient(app) as client:
        _select_and_enable(client)
        client.put(
            "/api/v1/modules/code_shop/projects/101/checkout",
            json={"path": str(checkout)},
        )
        task = _create_task(client)
        client.put(
            "/api/v1/modules/code_shop/projects/101/authority/checkout_write",
            json={"policy": "ask"},
        )
        asked = client.post(
            "/api/v1/modules/code_shop/execution/evaluate",
            json={
                "task_id": task["id"],
                "repository_id": "101",
                "action": "checkout_write",
                "capability": "repo.write",
                "idempotency_key": "ask",
            },
        )
        project_after_ask = client.get(
            "/api/v1/modules/code_shop/projects"
        ).json()[0]
        client.patch(
            "/api/v1/modules/code_shop/projects/101",
            json={"lifecycle": "enabled"},
        )
        client.put(
            "/api/v1/modules/code_shop/projects/101/authority/deployment",
            json={"policy": "allow"},
        )
        risky = client.post(
            "/api/v1/modules/code_shop/execution/evaluate",
            json={
                "task_id": task["id"],
                "repository_id": "101",
                "action": "deployment",
                "capability": "shell.execute",
                "idempotency_key": "deploy",
            },
        )
        client.patch(
            "/api/v1/modules/code_shop/projects/101",
            json={"lifecycle": "enabled"},
        )
        client.put(
            "/api/v1/modules/code_shop/projects/101/authority/checkout_write",
            json={"policy": "allow"},
        )
        untrusted = client.post(
            "/api/v1/modules/code_shop/execution/evaluate",
            json={
                "module_id": "user_supplied_module",
                "task_id": task["id"],
                "repository_id": "101",
                "action": "checkout_write",
                "capability": "repo.write",
                "idempotency_key": "untrusted",
            },
        )

    assert asked.json()["effective_decision"] == "request_attention"
    assert project_after_ask["lifecycle"] == "needs_attention"
    assert risky.json()["effective_decision"] == "request_attention"
    assert "attention_required_high_risk_action" in risky.json()["risk_findings"]
    assert untrusted.json()["effective_decision"] == "deny"
    assert "not manager-trusted" in untrusted.json()["reason"]


def test_model_blind_task_contract_and_failed_attempt_escalation_survive_restart(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    settings = Settings(data_dir=data, code_shop_checkout_roots=(tmp_path,))
    app = create_app(settings, code_shop_connector=_connector())

    with TestClient(app) as client:
        _select_and_enable(client)
        rejected = client.post(
            "/api/v1/modules/code_shop/tasks",
            json={
                "repository_id": "101",
                "title": "Should reject model routing",
                "capability": "debugging",
                "model": "some-model",
            },
        )
        task = _create_task(client)
        final = None
        for number in range(3):
            final = client.post(
                f"/api/v1/modules/code_shop/tasks/{task['id']}/attempts",
                json={
                    "status": "failed",
                    "approach": f"attempt {number + 1}",
                    "outcome": {"error": "bounded failure"},
                    "max_failed_attempts": 3,
                },
            )
        assert final is not None
        escalation = final.json()["escalation"]

    restarted = create_app(settings, code_shop_connector=_connector())
    with TestClient(restarted) as client:
        tasks = client.get("/api/v1/modules/code_shop/tasks").json()
        escalations = client.get("/api/v1/modules/code_shop/escalations").json()
        projects = client.get("/api/v1/modules/code_shop/projects").json()

    assert rejected.status_code == 422
    assert escalation["reason"] == "bounded_attempt_limit_reached"
    assert any(item["id"] == task["id"] for item in tasks)
    assert escalations[0]["task_id"] == task["id"]
    assert projects[0]["lifecycle"] == "needs_attention"
