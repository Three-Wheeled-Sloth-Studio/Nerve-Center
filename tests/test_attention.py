from pathlib import Path

from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.code_shop.domain import GitHubRepositoryIdentity
from nerve_center.code_shop.github import StaticGitHubRepositoryConnector
from nerve_center.config import Settings


def test_attention_submission_is_idempotent_and_survives_restart(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)

    payload = {
        "kind": "attention",
        "module_id": "example_module",
        "source_type": "workflow_blocker",
        "source_id": "blocker-1",
        "idempotency_key": "blocker-1-v1",
        "title": "Needs a decision",
        "summary": "A bounded workflow branch needs user input.",
        "context": {"fact": "preserved"},
        "allowed_dispositions": ["continue", "stop"],
        "validation": {"check": "module-owned"},
        "downstream_meaning": {"continue": "resume dependency"},
        "dependency_keys": ["example:branch:1"],
    }

    with TestClient(app) as client:
        first = client.post("/api/v1/attention", json=payload)
        duplicate = client.post(
            "/api/v1/attention",
            json={**payload, "title": "Changed duplicate payload"},
        )
        item_id = first.json()["item"]["id"]
        blocked = client.get(
            "/api/v1/attention/dependencies/example:branch:1/blocked"
        )
        unrelated_run = client.post(
            "/api/v1/runs",
            json={"task_id": "synthetic", "duration_seconds": 60},
        )

    restarted = create_app(settings)
    with TestClient(restarted) as client:
        fetched = client.get(f"/api/v1/attention/{item_id}")
        history = client.get(f"/api/v1/attention/{item_id}/history")

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert duplicate.json()["created"] is False
    assert duplicate.json()["item"]["id"] == item_id
    assert duplicate.json()["item"]["title"] == "Needs a decision"
    assert blocked.json()["blocked"] is True
    assert unrelated_run.status_code == 201
    assert fetched.json()["context"] == {"fact": "preserved"}
    assert [event["event_type"] for event in history.json()] == ["created"]


def test_resolution_unblocks_only_declared_dependency_and_records_history(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/attention",
            json={
                "kind": "review",
                "module_id": "example_module",
                "source_type": "review",
                "source_id": "review-1",
                "idempotency_key": "review-1",
                "title": "Review output",
                "summary": "Review only this branch.",
                "allowed_dispositions": ["accept", "revise"],
                "dependency_keys": ["example:branch:review"],
            },
        ).json()["item"]
        unrelated_before = client.get(
            "/api/v1/attention/dependencies/example:branch:other/blocked"
        )
        resolved = client.post(
            f"/api/v1/attention/{created['id']}/resolve",
            json={
                "disposition": "accept",
                "detail": {"note": "reviewed"},
                "actor": "user",
            },
        )
        blocked_after = client.get(
            "/api/v1/attention/dependencies/example:branch:review/blocked"
        )
        history = client.get(
            f"/api/v1/attention/{created['id']}/history"
        ).json()

    assert created["kind"] == "review"
    assert unrelated_before.json()["blocked"] is False
    assert resolved.json()["state"] == "resolved"
    assert resolved.json()["resolution"]["disposition"] == "accept"
    assert blocked_after.json()["blocked"] is False
    assert [event["event_type"] for event in history] == ["created", "resolved"]


def test_module_attention_payload_cannot_grant_code_shop_authority(
    tmp_path: Path,
) -> None:
    connector = StaticGitHubRepositoryConnector(
        [
            GitHubRepositoryIdentity(
                repository_id="101",
                full_name="Three-Wheeled-Sloth-Studio/Nerve-Center",
                visibility="public",
                default_branch="main",
            )
        ]
    )
    app = create_app(
        Settings(data_dir=tmp_path),
        code_shop_connector=connector,
    )

    with TestClient(app) as client:
        client.post("/api/v1/modules/code_shop/projects/101/select")
        created = client.post(
            "/api/v1/attention",
            json={
                "kind": "attention",
                "module_id": "user_module",
                "source_type": "request",
                "source_id": "1",
                "idempotency_key": "cannot-grant",
                "title": "Pretend grant",
                "summary": "Descriptive data only.",
                "context": {
                    "policy": "allow",
                    "capability": "shell.execute",
                    "official": True,
                },
                "allowed_dispositions": ["grant_everything"],
            },
        ).json()["item"]
        client.post(
            f"/api/v1/attention/{created['id']}/resolve",
            json={"disposition": "grant_everything"},
        )
        policies = client.get(
            "/api/v1/modules/code_shop/projects/101/authority"
        ).json()
        trust = client.get("/api/v1/modules/code_shop/trust").json()

    assert policies == []
    assert trust == {
        "module_id": "code_shop",
        "official": True,
        "source": "builtin_registry",
    }
