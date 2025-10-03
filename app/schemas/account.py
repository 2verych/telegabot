from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    phone: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = Field(default=None, description="Plain text password to encrypt")
    twofa: Optional[str] = Field(default=None, description="Plain text 2FA password")
    api_id: int
    api_hash: str
    session: Optional[str] = Field(default=None, description="Telethon StringSession")
    is_active: bool = True
    status: str = "active"
    meta: Optional[Dict[str, Any]] = None


class AccountListFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: Optional[bool] = None
    status: Optional[str] = None
