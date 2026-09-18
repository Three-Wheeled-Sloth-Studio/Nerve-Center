from pathlib import Path

from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.code_shop.domain import GitHubRepositoryIdentity
from nerve_center.code_shop.github import StaticGitHubRepositoryConnector
from nerve_center.config import Settings
from nerve_center.persistence.database import Database
from nerve_center.persistence.resource_profiles import ResourceProfileRepository
from nerve_center.resource_profiles.domain import MANAGER_DEFAULT_PROFILE_ID
from nerve_center.resource_profiles.service import ResourceProfileService


def _service(tmp_path: Path) -> ResourceProfileService:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    service = ResourceProfileService(ResourceProfileRepository(database))
    service.initialize()
    return service


def _approve_required_job_scout_permissions(client: TestClient) -> None:
    reviews = client.get(
        "/api/v1/module-permissions",
        params={"module_id": "job_scout"},
    ).json()
    assert len(reviews) == 1
    review = reviews[0]
    for permission in review["permissions"]:
        if not permission["required"]:
            continue
        response = client.post(
            f"/api/v1/module-permissions/{review['id']}/permissions/"
            f"{permission['key']}/approve",
            json={"actor": "resource-profile-test", "provenance": {"source": "test"}},
        )
        assert response.status_code == 200
    enabled = client.patch(
        "/api/v1/modules/job_scout",
        json={"lifecycle_state": "enabled"},
    )
    assert enabled.status_code == 200


def test_profile_resolution_persists_and_reports_enforcement(tmp_path: Path) -> None:
    service = _service(tmp_path)
    default = service.selected()
    created = service.create(
        "Quiet",
        {
            "max_requests": 40,
            "max_memory_mb": 4096,
            "max_cloud_spend_usd": 2.5,
        },
    )
    service.select(created["id"])

    effective = service.resolve(
        overrides={
            "max_requests": 20,
            "max_vram_mb": 2048,
        }
    )

    assert default["id"] == MANAGER_DEFAULT_PROFILE_ID
    assert effective.profile_id == created["id"]
    assert effective.limits["max_requests"] == 20
    assert effective.limits["max_llm_calls"] == 100
    assert effective.limits["max_memory_mb"] == 4096
    assert effective.limits["max_vram_mb"] == 2048
    assert effective.enforcement["max_requests"] == "enforced"
    assert effective.enforcement["max_memory_mb"] == "unenforced"
    assert effective.enforcement["max_cloud_spend_usd"] == "unenforced_no_authority"
    assert effective.source_by_field["max_requests"] == "session_override"
    assert effective.source_by_field["max_memory_mb"] == f"profile:{created['id']}"
    assert effective.authorizes_cloud_spend is False

    restarted = _service(tmp_path)
    assert restarted.selected()["id"] == created["id"]
    assert restarted.resolve().limits["max_memory_mb"] == 4096


def test_resource_profile_api_crud_selection_and_validation(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        initial = client.get("/api/v1/resource-profiles")
        created = client.post(
            "/api/v1/resource-profiles",
            json={
                "display_name": "Overnight",
                "limits": {
                    "max_requests": 60,
                    "max_parallel_work": 2,
                    "max_memory_mb": 8192,
                },
            },
        )
        profile_id = created.json()["id"]
        updated = client.patch(
            f"/api/v1/resource-profiles/{profile_id}",
            json={
                "display_name": "Overnight Conservative",
                "limits": {
                    "max_requests": 50,
                    "max_parallel_work": 2,
                    "max_memory_mb": 8192,
                },
            },
        )
        selected = client.post(f"/api/v1/resource-profiles/{profile_id}/select")
        current = client.get("/api/v1/resource-profiles/selected")
        resolved = client.post(
            "/api/v1/resource-profiles/resolve",
            json={
                "overrides": {
                    "max_requests": 25,
                    "max_exploration_units": 100,
                }
            },
        )
        invalid_zero = client.post(
            "/api/v1/resource-profiles",
            json={"display_name": "Invalid", "limits": {"max_requests": 0}},
        )
        invalid_unknown = client.post(
            "/api/v1/resource-profiles",
            json={"display_name": "Invalid", "limits": {"mystery_limit": 1}},
        )

    assert initial.status_code == 200
    assert initial.json()[0]["id"] == MANAGER_DEFAULT_PROFILE_ID
    assert created.status_code == 201
    assert updated.json()["display_name"] == "Overnight Conservative"
    assert selected.json()["selected"] is True
    assert current.json()["id"] == profile_id
    assert resolved.json()["profile_id"] == profile_id
    assert resolved.json()["limits"]["max_requests"] == 25
    assert resolved.json()["limits"]["max_memory_mb"] == 8192
    assert resolved.json()["enforcement"]["max_exploration_units"] == "unenforced"
    assert invalid_zero.status_code == 422
    assert invalid_unknown.status_code == 422


def test_selected_profile_and_session_override_drive_real_run_budget(
    tmp_path: Path,
) -> None:
    app = create_app(Settings(data_dir=tmp_path))

    with TestClient(app) as client:
        _approve_required_job_scout_permissions(client)
        profile = client.post(
            "/api/v1/resource-profiles",
            json={
                "display_name": "Bounded",
                "limits": {
                    "max_requests": 12,
                    "max_llm_calls": 4,
                    "max_parallel_work": 1,
                    "max_memory_mb": 4096,
                    "max_cloud_spend_usd": 1.0,
                },
            },
        ).json()
        client.post(f"/api/v1/resource-profiles/{profile['id']}/select")

        session = client.post(
            "/api/v1/sessions",
            json={
                "duration_seconds": 60,
                "resource_overrides": {
                    "max_requests": 5,
                    "max_vram_mb": 2048,
                },
            },
        )
        session_body = session.json()
        run_id = session_body["module_run_ids"]["job_scout"]
        run = client.get(f"/api/v1/runs/{run_id}").json()

        configured_run = client.post(
            "/api/v1/runs",
            json={
                "task_id": "job_scout.discovery",
                "duration_seconds": 60,
                "configuration": {
                    "max_requests": 99999,
                    "max_llm_calls": 99999,
                    "max_parallel_work": 99,
                },
            },
        )
        client.post(f"/api/v1/sessions/{session_body['id']}/emergency-stop")

    assert session.status_code == 201
    assert session_body["resource_profile_id"] == profile["id"]
    assert session_body["resource_policy"] == {
        "max_requests": 5,
        "max_llm_calls": 4,
        "max_parallel_work": 1,
    }
    assert session_body["effective_resource_limits"]["max_memory_mb"] == 4096
    assert session_body["effective_resource_limits"]["max_vram_mb"] == 2048
    assert session_body["resource_enforcement"]["max_memory_mb"] == "unenforced"
    assert session_body["resource_enforcement"]["max_cloud_spend_usd"] == (
        "unenforced_no_authority"
    )
    assert run["budget"] == {
        "max_requests": 5,
        "max_llm_calls": 4,
        "max_parallel_work": 1,
    }
    assert configured_run.status_code == 201
    assert configured_run.json()["budget"] == {
        "max_requests": 12,
        "max_llm_calls": 4,
        "max_parallel_work": 1,
    }


def _connector() -> StaticGitHubRepositoryConnector:
    return StaticGitHubRepositoryConnector(
        [
            GitHubRepositoryIdentity(
                repository_id="101",
                full_name="Three-Wheeled-Sloth-Studio/Nerve-Center",
                visibility="public",
                default_branch="main",
            )
        ]
    )


def _checkout(root: Path) -> Path:
    path = root / "Nerve-Center"
    (path / ".git").mkdir(parents=True)
    (path / ".git" / "config").write_text(
        '[remote "origin"]\n'
        "    url = git@github.com:Three-Wheeled-Sloth-Studio/Nerve-Center.git\n",
        encoding="utf-8",
    )
    return path


def test_resource_profile_does_not_grant_module_permission_or_code_shop_authority(
    tmp_path: Path,
) -> None:
    approved_root = tmp_path / "approved"
    approved_root.mkdir()
    checkout = _checkout(approved_root)
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            code_shop_checkout_roots=(approved_root,),
        ),
        code_shop_connector=_connector(),
    )

    with TestClient(app) as client:
        profile = client.post(
            "/api/v1/resource-profiles",
            json={
                "display_name": "Large",
                "limits": {
                    "max_requests": 5000,
                    "max_llm_calls": 500,
                    "max_parallel_work": 20,
                    "max_cloud_spend_usd": 100.0,
                },
            },
        ).json()
        client.post(f"/api/v1/resource-profiles/{profile['id']}/select")

        permission_bypass = client.patch(
            "/api/v1/modules/job_scout",
            json={"lifecycle_state": "enabled"},
        )

        client.post("/api/v1/modules/code_shop/projects/101/select")
        client.patch(
            "/api/v1/modules/code_shop/projects/101",
            json={"lifecycle": "enabled"},
        )
        linked = client.put(
            "/api/v1/modules/code_shop/projects/101/checkout",
            json={"path": str(checkout)},
        )
        task = client.post(
            "/api/v1/modules/code_shop/tasks",
            json={
                "repository_id": "101",
                "title": "Resource boundary",
                "capability": "code_implementation",
                "source_backlog": {"issue": 64},
            },
        ).json()
        evaluation = client.post(
            "/api/v1/modules/code_shop/execution/evaluate",
            json={
                "task_id": task["id"],
                "repository_id": "101",
                "action": "checkout_write",
                "capability": "repo.write",
                "resource_paths": ["src/example.py"],
                "idempotency_key": "resource-profile-boundary",
            },
        )
        policies = client.get(
            "/api/v1/modules/code_shop/projects/101/authority"
        ).json()
        resolved = client.post("/api/v1/resource-profiles/resolve", json={}).json()

    assert permission_bypass.status_code == 422
    assert linked.status_code == 200
    assert evaluation.json()["effective_decision"] != "execute"
    assert policies == []
    assert resolved["authorizes_cloud_spend"] is False
