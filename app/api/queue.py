from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key
from app.core.config import settings
from app.core.errors import ServiceError
from app.core.security import EncryptionService
from app.db.session import get_session
from app.models.models import BotRuleset
from app.schemas.common import JobResponse
from app.schemas.queue import ActionEnqueue, OpenChannelEnqueue, ReadPostEnqueue, RulesetRunRequest
from app.services.job_service import JobService

router = APIRouter(prefix="/api/v1/queue", tags=["queue"], dependencies=[Depends(require_api_key)])

encryptor = EncryptionService(settings.kms_key_bytes)


@router.post("/login", response_model=JobResponse)
def enqueue_login(request: ActionEnqueue) -> JobResponse:
    with get_session() as session:
        service = JobService(session, encryptor)
        return service.enqueue_action(request.accountId, "LOGIN", {})


@router.post("/logout", response_model=JobResponse)
def enqueue_logout(request: ActionEnqueue) -> JobResponse:
    with get_session() as session:
        service = JobService(session, encryptor)
        return service.enqueue_action(request.accountId, "LOGOUT", {})


@router.post("/channels/open", response_model=JobResponse)
def enqueue_open_channel(request: OpenChannelEnqueue) -> JobResponse:
    payload = request.model_dump(by_alias=True)
    account_id = payload.pop("accountId")
    with get_session() as session:
        service = JobService(session, encryptor)
        return service.enqueue_action(account_id, "OPEN_CHANNEL", payload)


@router.post("/posts/read", response_model=JobResponse)
def enqueue_read_post(request: ReadPostEnqueue) -> JobResponse:
    payload = request.model_dump(by_alias=True)
    account_id = payload.pop("accountId")
    with get_session() as session:
        service = JobService(session, encryptor)
        return service.enqueue_action(account_id, "READ_POST", payload)


@router.post("/rulesets/{ruleset_id}/run", response_model=JobResponse)
def run_ruleset(ruleset_id: int, request: RulesetRunRequest) -> JobResponse:
    with get_session() as session:
        ruleset = session.get(BotRuleset, ruleset_id)
        if not ruleset:
            raise ServiceError(code="RULESET_NOT_FOUND", message="Ruleset not found", http_status=404)
        account_id = request.accountId or ruleset.account_id
        if not account_id:
            raise ServiceError(code="ACCOUNT_REQUIRED", message="Account is required for ruleset")
        context = request.context or {}
        service = JobService(session, encryptor)
        return service.enqueue_ruleset(ruleset, account_id, context)
