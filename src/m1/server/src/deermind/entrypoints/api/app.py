"""API process and health endpoints; no business handlers or database startup yet."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from deermind.bootstrap.settings import Settings
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.files.check import check_storage
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

LOGGER = logging.getLogger("runtime")


class Health(BaseModel):
    """Only the API and mounted file storage are covered in this increment."""

    status: str


def create_app() -> FastAPI:
    """OpenAPI export is offline; required configuration is checked on startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        settings = Settings.from_environment()
        check_storage(settings.files_root)
        app.state.settings = settings
        LOGGER.info(
            "API 已启动，共享文件目录可读写",
            extra={"action": "api_started", "outcome": "success"},
        )
        yield
        LOGGER.info("API 已停止", extra={"action": "api_stopped", "outcome": "success"})

    app = FastAPI(title="DeerMind M1", version="0.1.0", lifespan=lifespan)

    @app.get("/health/live", response_model=Health, operation_id="health_live")
    def live() -> Health:
        return Health(status="ok")

    @app.get("/health/ready", response_model=Health, operation_id="health_ready")
    def ready() -> Health:
        try:
            settings: Settings = app.state.settings
            check_storage(settings.files_root)
        except OSError as error:
            LOGGER.error(
                "共享文件目录不可用",
                extra={
                    "action": "storage_check",
                    "outcome": "failed",
                    "error_code": "STORAGE_UNAVAILABLE",
                },
                exc_info=True,
            )
            raise HTTPException(status_code=503, detail="Storage unavailable") from error
        return Health(status="ok")

    return app


def main() -> None:
    configure_logging()
    uvicorn.run(
        "deermind.entrypoints.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        log_config=None,
        access_log=False,
    )
