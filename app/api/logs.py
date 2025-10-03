from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.auth import require_api_key
from app.db.session import get_session
from app.services.logger_service import LoggerService

router = APIRouter(prefix="/api/v1/logs", tags=["logs"], dependencies=[Depends(require_api_key)])


@router.get("/actions")
def list_action_logs(
    account_id: int | None = Query(default=None, alias="accountId"),
    job_id: int | None = Query(default=None, alias="jobId"),
    level: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    with get_session() as session:
        service = LoggerService(session)
        return service.list_action_logs(account_id=account_id, job_id=job_id, level=level, limit=limit)


@router.get("/errors")
def list_error_logs(
    account_id: int | None = Query(default=None, alias="accountId"),
    job_id: int | None = Query(default=None, alias="jobId"),
    error_code: str | None = Query(default=None, alias="errorCode"),
    limit: int = Query(default=100, le=500),
):
    with get_session() as session:
        service = LoggerService(session)
        return service.list_error_logs(account_id=account_id, job_id=job_id, error_code=error_code, limit=limit)
