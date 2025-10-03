from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import ActionLog, ErrorLog


class LoggerService:
    def __init__(self, session: Session):
        self.session = session

    def list_action_logs(
        self,
        *,
        account_id: Optional[int] = None,
        job_id: Optional[int] = None,
        level: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = select(ActionLog).order_by(ActionLog.created_at.desc()).limit(limit)
        if account_id is not None:
            query = query.where(ActionLog.account_id == account_id)
        if job_id is not None:
            query = query.where(ActionLog.job_id == job_id)
        if level is not None:
            query = query.where(ActionLog.level == level)
        logs = self.session.scalars(query).all()
        return [
            {
                "id": log.id,
                "jobId": log.job_id,
                "stepId": log.step_id,
                "accountId": log.account_id,
                "actionCode": log.action_code,
                "message": log.message,
                "level": log.level,
                "payload": log.payload,
                "createdAt": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]

    def list_error_logs(
        self,
        *,
        account_id: Optional[int] = None,
        job_id: Optional[int] = None,
        error_code: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit)
        if account_id is not None:
            query = query.where(ErrorLog.account_id == account_id)
        if job_id is not None:
            query = query.where(ErrorLog.job_id == job_id)
        if error_code is not None:
            query = query.where(ErrorLog.error_code == error_code)
        logs = self.session.scalars(query).all()
        return [
            {
                "id": log.id,
                "jobId": log.job_id,
                "stepId": log.step_id,
                "accountId": log.account_id,
                "errorCode": log.error_code,
                "message": log.message,
                "stack": log.stack,
                "context": log.context,
                "createdAt": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
