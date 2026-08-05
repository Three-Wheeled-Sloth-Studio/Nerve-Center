"""Browser-selected resume upload route for the Job Scout workspace."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, status

from nerve_center.config import Settings
from nerve_center.plugins.job_scout.settings import ResumeLoadRequest, ResumeUploadRequest
from nerve_center.profile.documents import MAX_DOCUMENT_BYTES, DocumentImportError
from nerve_center.providers.errors import ProviderError


def register_job_scout_upload_route(application: FastAPI, settings: Settings) -> None:
    @application.post(
        "/api/v1/modules/job_scout/resume/upload",
        status_code=status.HTTP_201_CREATED,
    )
    async def upload_resume(request: ResumeUploadRequest) -> object:
        safe_name = Path(request.file_name.replace("\\", "/")).name.strip()
        if not safe_name or safe_name in {".", ".."}:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_DOCUMENT_NAME",
                    "message": "Choose a resume file with a valid file name.",
                },
            )
        try:
            raw = base64.b64decode(request.content_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_DOCUMENT_UPLOAD",
                    "message": "The selected resume file could not be transferred.",
                },
            ) from error
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "DOCUMENT_TOO_LARGE",
                    "message": "Resume source files must be 25 MB or smaller.",
                },
            )

        import_root = settings.module_data_dir("job_scout") / "imports"
        import_dir = import_root / uuid4().hex
        import_dir.mkdir(parents=True, exist_ok=False)
        stored_path = import_dir / safe_name
        try:
            stored_path.write_bytes(raw)
            coordinator = application.state.job_scout_coordinator
            return await coordinator.load_resume(
                ResumeLoadRequest(
                    path=str(stored_path),
                    analyze_resume=request.analyze_resume,
                )
            )
        except (DocumentImportError, OSError) as error:
            stored_path.unlink(missing_ok=True)
            import_dir.rmdir()
            detail = (
                {"code": error.code, "message": str(error)}
                if isinstance(error, DocumentImportError)
                else {
                    "code": "DOCUMENT_ACCESS_FAILED",
                    "message": "The selected resume file could not be stored or read.",
                }
            )
            raise HTTPException(status_code=422, detail=detail) from error
        except ProviderError as error:
            raise HTTPException(status_code=503, detail=error.as_dict()) from error
