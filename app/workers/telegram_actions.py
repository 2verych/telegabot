from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Dict, Optional

from telethon import TelegramClient
from telethon import types  # type: ignore
from telethon.sessions import StringSession

from app.core.security import EncryptionService
from app.models.models import TelegramAccount
from app.workers.exceptions import ActionError


@dataclass
class ActionOutcome:
    output: Dict[str, Any]
    session_blob: Optional[bytes] = None
    session_changed: bool = False
    status: Optional[str] = None
    last_success_login_at: Optional[datetime] = None


class TelegramActionExecutor:
    def __init__(self, encryptor: EncryptionService):
        self.encryptor = encryptor

    def execute(self, account: TelegramAccount, action_code: str, payload: Dict[str, Any]) -> ActionOutcome:
        if action_code == "LOGIN":
            return self._run(self._login(account))
        if action_code == "LOGOUT":
            return self._run(self._logout(account))
        if action_code == "OPEN_CHANNEL":
            return self._run(self._open_channel(account, payload))
        if action_code == "READ_POST":
            return self._run(self._read_post(account, payload))
        raise ActionError("UNKNOWN_ACTION", f"Unsupported action {action_code}")

    def _run(self, coro: Awaitable[ActionOutcome]) -> ActionOutcome:
        return asyncio.run(coro)

    async def _create_client(self, account: TelegramAccount) -> TelegramClient:
        session_string = account.session_blob.decode("utf-8") if account.session_blob else None
        api_hash = self.encryptor.decrypt(account.api_hash_enc)
        if not api_hash:
            raise ActionError("MISSING_API_HASH", "API hash is required for Telegram actions")
        client = TelegramClient(StringSession(session_string), account.api_id, api_hash)
        await client.connect()
        return client

    async def _login(self, account: TelegramAccount) -> ActionOutcome:
        client = await self._create_client(account)
        try:
            if not await client.is_user_authorized():
                raise ActionError("LOGIN_CODE_REQUIRED", "Account requires interactive login")
            session_string = client.session.save()
            session_blob = session_string.encode("utf-8")
            return ActionOutcome(
                output={"sessionOk": True, "accountId": account.id},
                session_blob=session_blob,
                session_changed=session_blob != account.session_blob,
                status="online",
                last_success_login_at=datetime.utcnow(),
            )
        finally:
            await client.disconnect()

    async def _logout(self, account: TelegramAccount) -> ActionOutcome:
        client = await self._create_client(account)
        try:
            await client.log_out()
        finally:
            await client.disconnect()
        return ActionOutcome(
            output={"loggedOut": True},
            session_blob=None,
            session_changed=account.session_blob is not None,
            status="offline",
        )

    async def _open_channel(self, account: TelegramAccount, payload: Dict[str, Any]) -> ActionOutcome:
        channel_name = payload.get("channel")
        limit = int(payload.get("limit", 5))
        if not channel_name:
            raise ActionError("INVALID_INPUT", "Channel is required")
        client = await self._create_client(account)
        try:
            if not await client.is_user_authorized():
                raise ActionError("NOT_AUTHORIZED", "Account is not authorized")
            entity = await client.get_entity(channel_name)
            messages = await client.get_messages(entity, limit=limit)
            posts = []
            for message in messages:
                if not isinstance(message, (types.Message, types.MessageService)):
                    continue
                if isinstance(message, types.MessageService):
                    continue
                posts.append(
                    {
                        "id": str(message.id),
                        "date": message.date.isoformat() if message.date else None,
                        "text": message.message or "",
                        "views": getattr(message, "views", None),
                    }
                )
            session_string = client.session.save()
            session_blob = session_string.encode("utf-8")
            return ActionOutcome(
                output={
                    "channel": channel_name,
                    "posts": posts,
                    "total": len(posts),
                },
                session_blob=session_blob,
                session_changed=session_blob != account.session_blob,
            )
        finally:
            await client.disconnect()

    async def _read_post(self, account: TelegramAccount, payload: Dict[str, Any]) -> ActionOutcome:
        channel_name = payload.get("channel")
        post_id = payload.get("postId") or payload.get("post_id")
        if not channel_name or not post_id:
            raise ActionError("INVALID_INPUT", "Channel and postId are required")
        client = await self._create_client(account)
        try:
            if not await client.is_user_authorized():
                raise ActionError("NOT_AUTHORIZED", "Account is not authorized")
            entity = await client.get_entity(channel_name)
            try:
                message_id = int(post_id)
            except (TypeError, ValueError):
                raise ActionError("INVALID_POST_ID", "postId must be an integer")
            message = await client.get_messages(entity, ids=message_id)
            if not message:
                raise ActionError("POST_NOT_FOUND", f"Post {post_id} not found", retryable=False)
            post_data = {
                "id": str(message.id),
                "date": message.date.isoformat() if message.date else None,
                "text": message.message or "",
                "views": getattr(message, "views", None),
            }
            session_string = client.session.save()
            session_blob = session_string.encode("utf-8")
            return ActionOutcome(
                output={"channel": channel_name, "post": post_data},
                session_blob=session_blob,
                session_changed=session_blob != account.session_blob,
            )
        finally:
            await client.disconnect()
