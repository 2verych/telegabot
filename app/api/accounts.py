from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.auth import require_api_key
from app.core.config import settings
from app.core.errors import ServiceError
from app.core.security import EncryptionService
from app.db.session import get_session
from app.schemas.account import AccountCreate, AccountListFilters
from app.schemas.common import AccountDetails, AccountSummary
from app.services.account_service import AccountService

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"], dependencies=[Depends(require_api_key)])

encryptor = EncryptionService(settings.kms_key_bytes)


@router.post("", response_model=AccountSummary)
def create_account(payload: AccountCreate) -> AccountSummary:
    with get_session() as session:
        service = AccountService(session, encryptor)
        return service.create_account(payload)


@router.get("", response_model=list[AccountSummary])
def list_accounts(
    is_active: bool | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list[AccountSummary]:
    filters = AccountListFilters(is_active=is_active, status=status)
    with get_session() as session:
        service = AccountService(session, encryptor)
        return service.list_accounts(filters)


@router.get("/{account_id}", response_model=AccountDetails)
def get_account(account_id: int) -> AccountDetails:
    with get_session() as session:
        service = AccountService(session, encryptor)
        try:
            return service.get_account_details(account_id)
        except ValueError as exc:
            raise ServiceError(code="ACCOUNT_NOT_FOUND", message=str(exc), http_status=404)
