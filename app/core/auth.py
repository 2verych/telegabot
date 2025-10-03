from fastapi import Depends, Header

from app.core.config import settings
from app.core.errors import ServiceError


async def verify_api_key(x_api_key: str = Header(..., alias="x-api-key")) -> None:
    if x_api_key != settings.api_key:
        raise ServiceError(code="UNAUTHORIZED", message="Invalid API key", http_status=401)


def require_api_key(_: None = Depends(verify_api_key)) -> None:
    return None
