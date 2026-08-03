from pathlib import Path

from nerve_center.config import Settings
from nerve_center.persistence.database import Database, SCHEMA_VERSION
from nerve_center.persistence.profile import CareerProfileRepository, SourceDocumentRepository
from nerve_center.profile.documents import import_source_document
from nerve_center.profile.models import CanonicalCareerProfile


def test_profile_and_document_persist_outside_checkout(tmp_path: Path) -> None:
    data_dir = tmp_path / "runtime"
    settings = Settings(data_dir=data_dir)
    database = Database(settings)
    database.initialize()

    source = tmp_path / "resume.txt"
    source.write_text("Synthetic product manager resume.\n", encoding="utf-8")
    document = import_source_document(source)
    SourceDocumentRepository(database).save(document)
    profile_store = CareerProfileRepository(database)
    profile_store.save_profile(CanonicalCareerProfile(version=1))

    assert settings.database_path.parent == data_dir
    assert SourceDocumentRepository(database).get(document.id).sha256 == document.sha256
    assert profile_store.get_profile().version == 1
    with database.engine.connect() as connection:
        version = connection.exec_driver_sql("SELECT version FROM schema_state").scalar_one()
    assert version == SCHEMA_VERSION
