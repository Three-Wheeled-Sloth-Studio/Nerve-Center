"""Local API routes for Ollama and canonical career profile workflows."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from nerve_center.api.schemas import (
    ClaimOverrideRequest,
    DocumentRegisterRequest,
    HypothesisDecisionRequest,
    ProfileExtractRequest,
)
from nerve_center.config import Settings
from nerve_center.persistence.database import Database
from nerve_center.persistence.profile import CareerProfileRepository, SourceDocumentRepository
from nerve_center.persistence.providers import ProviderCallRepository
from nerve_center.profile.documents import DocumentImportError, import_source_document
from nerve_center.profile.models import CanonicalCareerProfile, SourceDocument
from nerve_center.profile.service import CareerProfileService
from nerve_center.providers.base import ProviderModel, StructuredProvider
from nerve_center.providers.errors import ProviderError
from nerve_center.providers.ollama import OllamaProvider


def register_profile_routes(
    application: FastAPI,
    database: Database,
    settings: Settings,
    provider: StructuredProvider | None = None,
) -> None:
    document_repository = SourceDocumentRepository(database)
    profile_repository = CareerProfileRepository(database)
    runtime_provider = provider or OllamaProvider(
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.ollama_timeout_seconds,
        telemetry=ProviderCallRepository(database),
    )
    profile_service = CareerProfileService(profile_repository, runtime_provider)

    application.state.document_repository = document_repository
    application.state.profile_repository = profile_repository
    application.state.provider = runtime_provider

    @application.get("/api/v1/providers/ollama/models")
    async def list_ollama_models() -> list[ProviderModel]:
        try:
            return await runtime_provider.list_models()
        except ProviderError as error:
            raise _provider_http_error(error) from error

    @application.post(
        "/api/v1/profile/documents",
        status_code=status.HTTP_201_CREATED,
    )
    def register_profile_document(request: DocumentRegisterRequest) -> SourceDocument:
        try:
            document = import_source_document(Path(request.path))
            return document_repository.save(document)
        except (DocumentImportError, OSError) as error:
            detail = (
                {"code": error.code, "message": str(error)}
                if isinstance(error, DocumentImportError)
                else {
                    "code": "DOCUMENT_ACCESS_FAILED",
                    "message": "The file could not be read.",
                }
            )
            raise HTTPException(status_code=422, detail=detail) from error

    @application.get("/api/v1/profile/documents")
    def list_profile_documents() -> list[SourceDocument]:
        return document_repository.list()

    @application.get("/api/v1/profile")
    def get_profile() -> CanonicalCareerProfile:
        return profile_repository.get_profile()

    @application.post("/api/v1/profile/extract")
    async def extract_profile(request: ProfileExtractRequest) -> CanonicalCareerProfile:
        try:
            document = document_repository.get(request.document_id)
            return await profile_service.extract_document(document, model=request.model)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ProviderError as error:
            raise _provider_http_error(error) from error

    @application.post("/api/v1/profile/hypotheses/{hypothesis_id}/decision")
    def decide_hypothesis(
        hypothesis_id: str,
        request: HypothesisDecisionRequest,
    ) -> CanonicalCareerProfile:
        try:
            return profile_service.decide_hypothesis(hypothesis_id, request.decision)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @application.put("/api/v1/profile/claims/{claim_id}")
    def override_claim(
        claim_id: str,
        request: ClaimOverrideRequest,
    ) -> CanonicalCareerProfile:
        try:
            return profile_service.override_claim(
                claim_id,
                label=request.label,
                statement=request.statement,
                category=request.category,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error


def _provider_http_error(error: ProviderError) -> HTTPException:
    if error.code == "OLLAMA_UNREACHABLE":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=status_code, detail=error.as_dict())
