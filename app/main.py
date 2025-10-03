from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import accounts, health, jobs, logs, queue, rulesets
from app.core.errors import ServiceError


def create_app() -> FastAPI:
    app = FastAPI(title="Telegabot Service", version="1.0.0")

    app.include_router(health.router)
    app.include_router(accounts.router)
    app.include_router(queue.router)
    app.include_router(rulesets.router)
    app.include_router(jobs.router)
    app.include_router(logs.router)

    @app.exception_handler(ServiceError)
    async def handle_service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
        )

    @app.get("/")
    async def root():
        return {"service": "telegabot", "version": app.version}

    return app


app = create_app()
