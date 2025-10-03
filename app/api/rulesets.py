from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key
from app.core.errors import ServiceError
from app.db.session import get_session
from app.models.models import BotRuleset, TelegramAccount
from app.schemas.common import RulesetResponse
from app.schemas.ruleset import RulesetCreate

router = APIRouter(prefix="/api/v1/rulesets", tags=["rulesets"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=RulesetResponse)
def create_ruleset(payload: RulesetCreate) -> RulesetResponse:
    with get_session() as session:
        account_id = payload.account_id
        if account_id is not None:
            account = session.get(TelegramAccount, account_id)
            if not account:
                raise ServiceError(code="ACCOUNT_NOT_FOUND", message="Account not found", http_status=404)
        ruleset = BotRuleset(
            account_id=account_id,
            name=payload.name,
            schedule_cron=payload.schedule_cron,
            allow_parallel_for_account=payload.allow_parallel_for_account,
            is_enabled=payload.is_enabled,
            rule_json=payload.rule_json,
        )
        session.add(ruleset)
        session.flush()
        return RulesetResponse(
            id=ruleset.id,
            name=ruleset.name,
            account_id=ruleset.account_id,
            allow_parallel_for_account=ruleset.allow_parallel_for_account,
            schedule_cron=ruleset.schedule_cron,
            is_enabled=ruleset.is_enabled,
            rule_json=ruleset.rule_json,
        )
