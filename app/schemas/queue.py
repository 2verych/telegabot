from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


action_codes = {"LOGIN", "LOGOUT", "OPEN_CHANNEL", "READ_POST"}


class ActionEnqueue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accountId: int = Field(alias="accountId")


class OpenChannelEnqueue(ActionEnqueue):
    channel: str
    limit: int = Field(ge=1, le=100)


class ReadPostEnqueue(ActionEnqueue):
    channel: str
    postId: str = Field(alias="postId")


class RulesetRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: Optional[Dict[str, Any]] = None
    accountId: Optional[int] = Field(default=None, alias="accountId")
