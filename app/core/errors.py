from __future__ import annotations

from typing import Dict, Optional

from fastapi import HTTPException, status


class ServiceError(HTTPException):
    def __init__(self, code: str, message: str, http_status: int = status.HTTP_400_BAD_REQUEST, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(status_code=http_status, detail={"error": {"code": code, "message": message, "details": details or {}}})
        self.code = code
        self.message = message
        self.details = details or {}
