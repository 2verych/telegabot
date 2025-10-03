from __future__ import annotations

from typing import Any, Dict, Optional


class ActionError(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
