from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key
from app.core.config import settings
from app.core.security import EncryptionService
from app.db.session import get_session
from app.schemas.common import JobStatus, JobStepModel
from app.services.job_service import JobService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])

encryptor = EncryptionService(settings.kms_key_bytes)


@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: int) -> JobStatus:
    with get_session() as session:
        service = JobService(session, encryptor)
        return service.get_job_status(job_id)


@router.get("/{job_id}/steps", response_model=list[JobStepModel])
def get_job_steps(job_id: int) -> list[JobStepModel]:
    with get_session() as session:
        service = JobService(session, encryptor)
        return service.get_job_steps(job_id)


@router.post("/{job_id}/execute", response_model=JobStatus)
def execute_job(job_id: int) -> JobStatus:
    with get_session() as session:
        service = JobService(session, encryptor)
        return service.execute_job(job_id)
