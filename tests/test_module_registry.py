from pathlib import Path

import pytest

from nerve_center import __version__
from nerve_center.config import Settings
from nerve_center.domain.module import ModuleLifecycleState
from nerve_center.persistence.database import Database
from nerve_center.persistence.modules import ModuleRepository
from nerve_center.plugins.job_scout.manifest import job_scout_manifest
from nerve_center.plugins.synthetic import SyntheticTaskPlugin
from nerve_center.scheduler.registry import TaskRegistry


def test_registry_requires_manifest_declared_tasks() -> None:
    registry = TaskRegistry(core_version=__version__)

    with pytest.raises(ValueError, match="missing task implementations"):
        registry.register_module(job_scout_manifest(), [SyntheticTaskPlugin()])


def test_module_inventory_sync_preserves_user_lifecycle_choice(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    repository = ModuleRepository(database)
    manifest = job_scout_manifest()

    repository.synchronize([manifest])
    repository.set_lifecycle(manifest.module_id, ModuleLifecycleState.PAUSED)
    repository.synchronize([manifest])

    installed = repository.get(manifest.module_id)
    assert installed.lifecycle_state == ModuleLifecycleState.PAUSED
    assert installed.manifest == manifest
    assert (tmp_path / "modules" / manifest.storage_namespace).is_dir()


def test_undeclared_installed_module_is_reported_not_installed(tmp_path: Path) -> None:
    database = Database(Settings(data_dir=tmp_path))
    database.initialize()
    repository = ModuleRepository(database)
    manifest = job_scout_manifest()
    repository.synchronize([manifest])

    repository.synchronize([])

    assert repository.get(manifest.module_id).lifecycle_state == ModuleLifecycleState.NOT_INSTALLED
