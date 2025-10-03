from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RulesetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    account_id: Optional[int] = Field(default=None, alias="accountId")
    schedule_cron: Optional[str] = Field(default=None, alias="scheduleCron")
    allow_parallel_for_account: bool = Field(default=False, alias="allowParallelForAccount")
    is_enabled: bool = Field(default=True, alias="isEnabled")
    rule_json: Dict[str, Any] = Field(alias="rule")
