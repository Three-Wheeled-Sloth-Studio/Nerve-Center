"""Persistence repositories for local source documents and canonical profile state."""

from __future__ import annotations

from nerve_center.persistence.database import Database
from nerve_center.persistence.models import CareerProfileModel, SourceDocumentModel
from nerve_center.profile.models import CanonicalCareerProfile, SourceDocument


class SourceDocumentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, document: SourceDocument) -> SourceDocument:
        with self.database.session() as session:
            existing = session.get(SourceDocumentModel, document.id)
            values = {
                "source_path": document.source_path,
                "file_name": document.file_name,
                "format": document.format.value,
                "media_type": document.media_type,
                "sha256": document.sha256,
                "byte_size": document.byte_size,
                "modified_at": document.modified_at,
                "imported_at": document.imported_at,
                "segments": [item.model_dump(mode="json") for item in document.segments],
            }
            if existing is None:
                session.add(SourceDocumentModel(id=document.id, **values))
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
        return document

    def get(self, document_id: str) -> SourceDocument:
        with self.database.session() as session:
            model = session.get(SourceDocumentModel, document_id)
            if model is None:
                raise KeyError(f"unknown source document: {document_id}")
            return _document_from_model(model)

    def list(self) -> list[SourceDocument]:
        with self.database.session() as session:
            models = session.query(SourceDocumentModel).order_by(
                SourceDocumentModel.imported_at.desc()
            )
            return [_document_from_model(item) for item in models]


class CareerProfileRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_profile(self) -> CanonicalCareerProfile:
        with self.database.session() as session:
            model = session.get(CareerProfileModel, "canonical")
            if model is None:
                return CanonicalCareerProfile()
            return CanonicalCareerProfile.model_validate(model.payload)

    def save_profile(self, profile: CanonicalCareerProfile) -> CanonicalCareerProfile:
        with self.database.session() as session:
            model = session.get(CareerProfileModel, profile.id)
            payload = profile.model_dump(mode="json")
            if model is None:
                session.add(
                    CareerProfileModel(
                        id=profile.id,
                        version=profile.version,
                        updated_at=profile.updated_at,
                        payload=payload,
                    )
                )
            else:
                model.version = profile.version
                model.updated_at = profile.updated_at
                model.payload = payload
        return profile


def _document_from_model(model: SourceDocumentModel) -> SourceDocument:
    return SourceDocument.model_validate(
        {
            "id": model.id,
            "source_path": model.source_path,
            "file_name": model.file_name,
            "format": model.format,
            "media_type": model.media_type,
            "sha256": model.sha256,
            "byte_size": model.byte_size,
            "modified_at": model.modified_at,
            "imported_at": model.imported_at,
            "segments": model.segments,
        }
    )
