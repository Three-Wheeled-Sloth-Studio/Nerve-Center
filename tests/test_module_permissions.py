from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nerve_center.api.app import create_app
from nerve_center.code_shop.domain import GitHubRepositoryIdentity
from nerve_center.code_shop.github import StaticGitHubRepositoryConnector
from nerve_center.config import Settings
from nerve_center.domain.module import (
    MODULE_API_VERSION,
    MODULE_MANIFEST_VERSION,
    ModuleCompatibility,
    ModuleLaunchDefinition,
    ModuleLifecycleState,
    ModuleManifest,
    ModulePermission,
    ModulePermissionKind,
    ModuleTaskDeclaration,
)
from nerve_center.module_permissions.domain import (
    PermissionClass,
    PermissionDecision,
    PermissionReviewState,
)
from nerve_center.persistence.database import Database
from nerve_center.persistence.models import ModuleModel
from nerve_center.persistence.module_permissions import ModulePermissionReviewRepository
from nerve_center.persistence.modules import ModuleRepository


def _manifest(
    *,
    version: str = "1.0.0",
    permissions: tuple[ModulePermission, ...] = (),
) -> ModuleManifest:
    return ModuleManifest(
        manifest_version=MODULE_MANIFEST_VERSION,
        module_id="example_module",
        display_name="Example Module",
        description="Permission review test module.",
        version=version,
        compatibility=ModuleCompatibility(
            module_api_version=MODULE_API_VERSION,
            minimum_core_version="0.12.29",
            maximum_tested_core_version="0.12.99",
            data_schema_version=1,
        ),
        launch=ModuleLaunchDefinition(
            runtime="managed_python",
            entrypoint="example.module",
        ),
        storage_namespace="example_module",
        permissions=permissions,
        task_types=(
            ModuleTaskDeclaration(
                task_id="example_module.run",
                display_name="Run",
                work_classes=("deterministic",),
            ),
        ),
    )


def _public_required() -> ModulePermission:
    return ModulePermission(
        kind=ModulePermissionKind.PUBLIC_NETWORK_READ,
        scopes=("example.com",),
        rationale="Read a configured public source.",
        required=True,
    )


def _storage_required() -> ModulePermission:
    return ModulePermission(
        kind=ModulePermissionKind.ASSIGNED_STORAGE_WRITE,
        scopes=("example_module",),
        rationale="Persist module-owned state.",
        required=True,
    )


def _browser_optional() -> ModulePermission:
    return ModulePermission(
        kind=ModulePermissionKind.BROWSER_AUTOMATION,
        scopes=("public_read_only",),
        rationale="Read public pages when direct HTTP is insufficient.",
        required=False,
    )


def test_no_permission_module_needs_no_synthetic_review(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    repository = ModuleRepository(database)
    manifest = _manifest()

    installed = repository.synchronize([manifest])[0]

    assert installed.lifecycle_state == ModuleLifecycleState.ENABLED
    assert repository.permission_reviews.list(module_id=manifest.module_id) == []


def test_required_permission_blocks_enablement_until_approved_and_survives_restart(
    tmp_path: Path,
) -> None:
    settings = Settings(data_dir=tmp_path)
    database = Database(settings)
    database.initialize()
    repository = ModuleRepository(database)
    manifest = _manifest(permissions=(_public_required(),))

    installed = repository.synchronize([manifest])[0]
    review = repository.permission_reviews.list(module_id=manifest.module_id)[0]

    assert installed.lifecycle_state == ModuleLifecycleState.PAUSED
    assert review.state == PermissionReviewState.PENDING
    assert review.operationally_allowed is False
    with pytest.raises(ValueError, match="unapproved required permissions"):
        repository.set_lifecycle(manifest.module_id, ModuleLifecycleState.ENABLED)

    permission = review.permissions[0]
    approved = repository.permission_reviews.decide(
        review.id,
        permission.key,
        PermissionDecision.APPROVED,
        actor="tester",
        provenance={"source": "test"},
    )
    assert approved.operationally_allowed is True
    repository.set_lifecycle(manifest.module_id, ModuleLifecycleState.ENABLED)

    restarted_database = Database(settings)
    restarted_database.initialize()
    restarted = ModuleRepository(restarted_database)
    restarted.synchronize([manifest])
    persisted = restarted.permission_reviews.list(module_id=manifest.module_id)[0]

    assert persisted.decisions[permission.key]["actor"] == "tester"
    assert persisted.operationally_allowed is True
    assert restarted.get(manifest.module_id).lifecycle_state == ModuleLifecycleState.ENABLED


def test_optional_denial_does_not_block_after_required_permissions_are_approved(
    tmp_path: Path,
) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    repository = ModuleRepository(database)
    manifest = _manifest(permissions=(_public_required(), _browser_optional()))
    repository.synchronize([manifest])
    review = repository.permission_reviews.list(module_id=manifest.module_id)[0]
    by_kind = {item.kind: item for item in review.permissions}

    required = repository.permission_reviews.decide(
        review.id,
        by_kind[ModulePermissionKind.PUBLIC_NETWORK_READ].key,
        PermissionDecision.APPROVED,
        actor="tester",
        provenance={},
    )
    assert required.state == PermissionReviewState.PENDING
    assert required.operationally_allowed is True
    repository.set_lifecycle(manifest.module_id, ModuleLifecycleState.ENABLED)

    settled = repository.permission_reviews.decide(
        review.id,
        by_kind[ModulePermissionKind.BROWSER_AUTOMATION].key,
        PermissionDecision.DENIED,
        actor="tester",
        provenance={"reason": "not needed"},
    )
    assert settled.state == PermissionReviewState.APPROVED
    assert settled.operationally_allowed is True


def test_identical_permission_set_carries_forward_but_changed_set_becomes_pending(
    tmp_path: Path,
) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    repository = ModuleRepository(database)

    first = _manifest(version="1.0.0", permissions=(_public_required(),))
    repository.synchronize([first])
    first_review = repository.permission_reviews.list(module_id=first.module_id)[0]
    key = first_review.permissions[0].key
    repository.permission_reviews.decide(
        first_review.id,
        key,
        PermissionDecision.APPROVED,
        actor="tester",
        provenance={"ticket": "A"},
    )
    repository.set_lifecycle(first.module_id, ModuleLifecycleState.ENABLED)

    second = _manifest(version="1.0.1", permissions=(_public_required(),))
    repository.synchronize([second])
    second_review = repository.permission_reviews.latest_for_manifest(second)
    assert second_review is not None
    assert second_review.operationally_allowed is True
    assert second_review.decisions[key]["provenance"]["source"] == (
        "identical_permission_carry_forward"
    )
    assert repository.get(second.module_id).lifecycle_state == ModuleLifecycleState.ENABLED

    changed = _manifest(
        version="1.0.1",
        permissions=(_public_required(), _storage_required()),
    )
    repository.synchronize([changed])
    changed_review = repository.permission_reviews.latest_for_manifest(changed)
    assert changed_review is not None
    assert changed_review.permission_fingerprint != second_review.permission_fingerprint
    assert changed_review.operationally_allowed is False
    assert changed_review.state == PermissionReviewState.PENDING
    assert repository.get(changed.module_id).lifecycle_state == ModuleLifecycleState.PAUSED


def test_review_rejects_undeclared_and_prohibited_approvals(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    reviews = ModulePermissionReviewRepository(database)
    manifest = _manifest(
        permissions=(
            ModulePermission(
                kind=ModulePermissionKind.PROCESS,
                scopes=("arbitrary",),
                rationale="Request direct process access.",
            ),
        )
    )
    review = reviews.ensure_review(manifest)
    assert review is not None
    assert review.permissions[0].permission_class == PermissionClass.PROHIBITED_EXTERNAL_ACTION

    with pytest.raises(ValueError, match="not declared"):
        reviews.decide(
            review.id,
            "not-a-declared-permission",
            PermissionDecision.APPROVED,
            actor="tester",
            provenance={},
        )
    with pytest.raises(ValueError, match="prohibited external-action"):
        reviews.decide(
            review.id,
            review.permissions[0].key,
            PermissionDecision.APPROVED,
            actor="tester",
            provenance={},
        )


def test_schema13_existing_manifest_gets_explicit_migration_approval(
    tmp_path: Path,
) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    database.previous_schema_version = 13
    old = _manifest(version="1.0.0", permissions=(_public_required(),))
    now = datetime.now(UTC)
    with database.session() as session:
        session.add(
            ModuleModel(
                module_id=old.module_id,
                lifecycle_state=ModuleLifecycleState.ENABLED,
                saved_priority=10,
                manifest=old.to_dict(),
                installed_at=now,
                updated_at=now,
            )
        )

    repository = ModuleRepository(database)
    current = _manifest(version="1.0.1", permissions=(_public_required(),))
    repository.synchronize([current])
    reviews = repository.permission_reviews.list(module_id=current.module_id)
    current_review = repository.permission_reviews.latest_for_manifest(current)

    assert len(reviews) == 2
    assert current_review is not None
    assert current_review.operationally_allowed is True
    assert repository.get(current.module_id).lifecycle_state == ModuleLifecycleState.ENABLED
    assert any(
        decision["provenance"]["source"] == "schema14_migration"
        for review in reviews
        for decision in review.decisions.values()
    )


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


def test_permission_api_approves_only_manifest_requests_and_does_not_grant_code_shop_authority(
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
        modules = client.get("/api/v1/modules").json()
        job_scout = next(
            item for item in modules if item["manifest"]["module_id"] == "job_scout"
        )
        reviews = client.get(
            "/api/v1/module-permissions",
            params={"module_id": "job_scout"},
        ).json()
        review = reviews[0]
        for permission in review["permissions"]:
            if permission["required"]:
                approved = client.post(
                    f"/api/v1/module-permissions/{review['id']}/permissions/"
                    f"{permission['key']}/approve",
                    json={"actor": "tester", "provenance": {"source": "test"}},
                )
                assert approved.status_code == 200

        enabled = client.patch(
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
                "title": "Permission boundary",
                "capability": "code_implementation",
                "source_backlog": {"issue": 63},
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
                "idempotency_key": "permission-boundary",
            },
        )
        policies = client.get(
            "/api/v1/modules/code_shop/projects/101/authority"
        ).json()

    assert job_scout["lifecycle_state"] == "paused"
    assert linked.status_code == 200
    assert enabled.status_code == 200
    assert evaluation.json()["effective_decision"] != "execute"
    assert policies == []
