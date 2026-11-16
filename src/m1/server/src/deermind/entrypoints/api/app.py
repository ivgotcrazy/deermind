"""API健康与启动检查；数据库升级由独立部署Job执行。"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from deermind.bootstrap.authentication import configure_authentication
from deermind.bootstrap.database import database_lifespan
from deermind.bootstrap.settings import Settings
from deermind.entrypoints.api.auth import authentication_error, router
from deermind.entrypoints.api.body_limit import RequestBodyLimit
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.database.connection import DatabaseNotReady, check_database
from deermind.infrastructure.files.check import check_storage
from deermind.product.public.authentication import AuthError
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

LOGGER = logging.getLogger("runtime")


class Health(BaseModel):
    """报告就绪状态，不暴露连接配置或数据库内部信息。"""

    status: str


def create_app() -> FastAPI:
    """OpenAPI export is offline; required configuration is checked on startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        settings = Settings.from_environment()
        check_storage(settings.files_root, require_mount=settings.files_backend == "pvc")
        app.state.settings = settings
        try:
            async with database_lifespan() as engine:
                app.state.database = engine
                app.state.auth, app.state.auth_config = await configure_authentication(engine)
                LOGGER.info(
                    "API 已启动，数据库版本及共享文件目录检查通过",
                    extra={"action": "api_started", "outcome": "success"},
                )
                yield
        except Exception:
            LOGGER.exception(
                "API 启动或运行失败，请检查配置与数据库版本",
                extra={"action": "api_failed", "outcome": "failed", "error_code": "API_FAILED"},
            )
            raise RuntimeError("API dependency check failed") from None
        LOGGER.info("API 已停止", extra={"action": "api_stopped", "outcome": "success"})

    app = FastAPI(title="DeerMind M1", version="0.1.0", lifespan=lifespan)

    app.include_router(router)
    app.add_middleware(RequestBodyLimit)
    app.add_exception_handler(AuthError, authentication_error)
    app.add_exception_handler(RequestValidationError, authentication_error)
    app.add_exception_handler(SQLAlchemyError, authentication_error)

    @app.get("/health/live", response_model=Health, operation_id="health_live")
    def live() -> Health:
        return Health(status="ok")

    @app.get("/health/ready", response_model=Health, operation_id="health_ready")
    async def ready() -> Health:
        try:
            settings: Settings = app.state.settings
            check_storage(settings.files_root, require_mount=settings.files_backend == "pvc")
            await check_database(app.state.database)
        except (OSError, SQLAlchemyError, DatabaseNotReady) as error:
            LOGGER.error(
                "数据库或共享文件目录不可用",
                extra={
                    "action": "readiness_check",
                    "outcome": "failed",
                    "error_code": "DEPENDENCY_UNAVAILABLE",
                },
                exc_info=True,
            )
            raise HTTPException(status_code=503, detail="Dependency unavailable") from error
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
        proxy_headers=False,
    )
