from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    with get_session() as session:
        session.execute(text("SELECT 1"))
    return {"status": "ok", "build": settings.build_version}
