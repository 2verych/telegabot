from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import EncryptionService
from app.models.models import ActionLog, ErrorLog, Job, TelegramAccount
from app.schemas.account import AccountCreate, AccountListFilters
from app.schemas.common import AccountDetails, AccountSummary


class AccountService:
    def __init__(self, session: Session, encryptor: EncryptionService):
        self.session = session
        self.encryptor = encryptor

    def create_account(self, payload: AccountCreate) -> AccountSummary:
        meta = payload.meta.copy() if payload.meta else {}
        meta.setdefault("session_format", "telethon-string" if payload.session else "unknown")

        account = TelegramAccount(
            label=payload.label,
            phone=payload.phone,
            login=payload.login,
            password_enc=self.encryptor.encrypt(payload.password),
            twofa_enc=self.encryptor.encrypt(payload.twofa),
            api_id=payload.api_id,
            api_hash_enc=self.encryptor.encrypt(payload.api_hash),
            session_blob=payload.session.encode("utf-8") if payload.session else None,
            session_version=0,
            is_active=payload.is_active,
            status=payload.status,
            meta=meta,
            last_session_updated_at=datetime.utcnow() if payload.session else None,
        )
        self.session.add(account)
        self.session.flush()
        return self._account_to_summary(account)

    def list_accounts(self, filters: AccountListFilters) -> list[AccountSummary]:
        query = select(TelegramAccount)
        if filters.is_active is not None:
            query = query.where(TelegramAccount.is_active == filters.is_active)
        if filters.status is not None:
            query = query.where(TelegramAccount.status == filters.status)
        accounts = self.session.scalars(query.order_by(TelegramAccount.id)).all()
        results: list[AccountSummary] = []
        for account in accounts:
            results.append(self._account_to_summary(account))
        return results

    def get_account_details(self, account_id: int) -> AccountDetails:
        account = self.session.get(TelegramAccount, account_id)
        if not account:
            raise ValueError("Account not found")
        summary = self._account_to_summary(account)

        actions_query = (
            select(ActionLog)
            .where(ActionLog.account_id == account_id)
            .order_by(ActionLog.created_at.desc())
            .limit(10)
        )
        actions = [self._action_to_dict(row) for row in self.session.scalars(actions_query).all()]

        errors_query = (
            select(ErrorLog)
            .where(ErrorLog.account_id == account_id)
            .order_by(ErrorLog.created_at.desc())
            .limit(3)
        )
        errors = [self._error_to_dict(row) for row in self.session.scalars(errors_query).all()]

        return AccountDetails(**summary.model_dump(), actions=actions, errors=errors)

    def _account_to_summary(self, account: TelegramAccount) -> AccountSummary:
        last_job_id = self.session.scalar(
            select(Job.id)
            .where(Job.account_id == account.id)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        last_action_at = self.session.scalar(
            select(func.max(ActionLog.created_at)).where(ActionLog.account_id == account.id)
        )
        pending_jobs = self.session.scalar(
            select(func.count()).where(Job.account_id == account.id, Job.status == "pending")
        )
        return AccountSummary(
            id=account.id,
            label=account.label,
            phone=account.phone,
            login=account.login,
            is_active=account.is_active,
            status=account.status,
            last_success_login_at=self._dt(account.last_success_login_at),
            last_session_updated_at=self._dt(account.last_session_updated_at),
            last_error_at=self._dt(account.last_error_at),
            last_error_message=account.last_error_message,
            meta=account.meta,
            last_job=last_job_id,
            last_action_at=self._dt(last_action_at),
            pending_jobs=pending_jobs or 0,
        )

    def _action_to_dict(self, action: ActionLog) -> Dict[str, Any]:
        return {
            "id": action.id,
            "jobId": action.job_id,
            "stepId": action.step_id,
            "accountId": action.account_id,
            "actionCode": action.action_code,
            "message": action.message,
            "level": action.level,
            "payload": action.payload,
            "createdAt": self._dt(action.created_at),
        }

    def _error_to_dict(self, error: ErrorLog) -> Dict[str, Any]:
        return {
            "id": error.id,
            "jobId": error.job_id,
            "stepId": error.step_id,
            "accountId": error.account_id,
            "errorCode": error.error_code,
            "message": error.message,
            "stack": error.stack,
            "context": error.context,
            "createdAt": self._dt(error.created_at),
        }

    @staticmethod
    def _dt(value: Optional[datetime]) -> Optional[str]:
        if not value:
            return None
        return value.isoformat()
