"""API健康与启动检查；数据库升级由独立部署Job执行。"""

import logging
import os
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from typing import Literal, TypedDict
from uuid import UUID

import uvicorn
from deermind.bootstrap.accounts import configure_usage
from deermind.bootstrap.authentication import configure_authentication
from deermind.bootstrap.courses import (
    STUDENT_VIEWS,
    configure_conversation,
    configure_courses,
    configure_rounds,
    configure_student_turns,
)
from deermind.bootstrap.database import database_lifespan
from deermind.bootstrap.domain import configure_domain
from deermind.bootstrap.evaluation import (
    configure_activity_configs,
    configure_claims,
    configure_evaluation_basis,
    configure_targets,
)
from deermind.bootstrap.materials import (
    configure_chapter_associations,
    configure_domain_analysis,
    configure_domain_intake,
    configure_instances,
    configure_intake_processing,
    configure_material_adoptions,
    configure_material_assistant,
    configure_material_deletion,
    configure_material_intake,
    configure_materials,
)
from deermind.bootstrap.settings import Settings
from deermind.entrypoints.api.activity_configs import router as activity_router
from deermind.entrypoints.api.auth import router
from deermind.entrypoints.api.body_limit import RequestBodyLimit
from deermind.entrypoints.api.conversation import connect_realtime
from deermind.entrypoints.api.conversation import router as conversation_router
from deermind.entrypoints.api.courses import router as courses_router
from deermind.entrypoints.api.domain import router as domain_router
from deermind.entrypoints.api.errors import api_error
from deermind.entrypoints.api.evaluation import router as evaluation_router
from deermind.entrypoints.api.learning_targets import router as target_router
from deermind.entrypoints.api.materials import router as materials_router
from deermind.entrypoints.api.realtime import Realtime
from deermind.entrypoints.api.realtime import router as realtime_router
from deermind.entrypoints.api.receipts import router as receipts_router
from deermind.entrypoints.api.usage import router as usage_router
from deermind.foundation.system.events.view_notices import resolve_view_change
from deermind.foundation.system.logging import configure_logging
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.requests import RequestReceipts
from deermind.infrastructure.database.connection import DatabaseNotReady, check_database
from deermind.infrastructure.files.check import check_storage
from deermind.infrastructure.nats.connection import MessagingSettings
from deermind.infrastructure.nats.realtime import ViewNotices
from deermind.product.public.chapter_associations import CHAPTER_ACTION
from deermind.product.public.courses import CHECK_COURSE, CONFIRM_COURSE, OPEN_SPACE
from deermind.product.public.errors import RequestConflict
from deermind.product.public.learning_targets import SAVE_TARGET
from deermind.product.public.material_assistant import CONVERSE, DECIDE
from deermind.product.public.material_intake import SUBMIT_INTAKE
from deermind.product.public.materials import DELETE_MATERIAL, RECEIVE_MATERIAL
from deermind.spaces.domain.public import (
    CLASSIFY,
    CONFIRM_PATH_ACTION,
    EXTRACT,
    PROCESS_INTAKE,
    SAVE_ACTION,
    SAVE_INSTANCE,
)
from deermind.spaces.evaluation.public import MANAGE_CLAIM
from deermind.spaces.interaction.public import (
    CONTROL_ACTIVITY,
    HANDLE_INPUT,
    MANAGE_ACTIVITY,
    PREPARE_DETECTION,
    SUBMIT_ANSWER,
)
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

LOGGER = logging.getLogger("runtime")


class Health(BaseModel):
    """报告就绪状态，不暴露连接配置或数据库内部信息。"""

    status: str


class WebSocketOptions(TypedDict):
    """固定应用实际使用的 Uvicorn WebSocket 参数。"""

    ws: Literal["websockets"]
    ws_max_size: int
    ws_max_queue: int
    ws_ping_interval: None
    ws_per_message_deflate: bool


def websocket_options() -> WebSocketOptions:
    """底层限制按完整消息，连接保活由应用 ping 和 pong 维护。"""
    return {
        "ws": "websockets",
        "ws_max_size": 64 * 1024,
        "ws_max_queue": 8,
        "ws_ping_interval": None,
        "ws_per_message_deflate": False,
    }


def create_app(
    *,
    realtime: Realtime | None = None,
    view_routes: Mapping[tuple[str, str], frozenset[str]] | None = None,
) -> FastAPI:
    """OpenAPI export is offline; required configuration is checked on startup."""
    hub = realtime or Realtime()
    routes = dict(STUDENT_VIEWS if view_routes is None else view_routes)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        settings = Settings.from_environment()
        check_storage(settings.files_root, require_mount=settings.files_backend == "pvc")
        app.state.settings = settings
        try:
            async with database_lifespan() as engine:
                app.state.database = engine
                app.state.auth, app.state.auth_config = await configure_authentication(engine)
                app.state.usage = configure_usage(engine, settings.files_root)
                domain = configure_domain(
                    engine, settings.files_root, backend=settings.files_backend
                )
                app.state.domain = domain
                claims = configure_claims(engine, settings)
                app.state.claims = claims
                app.state.evaluation_basis = configure_evaluation_basis(claims)
                configs = configure_activity_configs(engine, settings)
                app.state.activity_configs = configs
                materials, app.state.uploads = configure_materials(engine, settings, domain)
                app.state.materials = materials
                targets = configure_targets(materials, claims)
                app.state.learning_targets = targets
                checks, spaces, applications = configure_courses(targets, configs)
                app.state.course_checks = checks
                app.state.course_spaces = spaces
                app.state.course_applications = applications
                conversation = configure_conversation(spaces, configs)
                app.state.conversation = conversation
                turns = configure_student_turns(
                    spaces, conversation, materials.attachments, settings, configs
                )
                app.state.student_turns = turns.requests
                app.state.detection_rounds = configure_rounds(turns)
                if realtime is None:
                    connect_realtime(hub, turns.requests)
                assistant = configure_material_assistant(engine, settings, materials)
                app.state.material_assistant = assistant
                deletion = configure_material_deletion(assistant)
                app.state.material_deletion = deletion
                chapters = configure_chapter_associations(materials)
                app.state.chapter_associations = chapters
                adoptions = configure_material_adoptions(materials)
                app.state.material_adoptions = adoptions
                intake = configure_material_intake(materials)
                app.state.material_intake = intake
                domain_intake = configure_domain_intake(materials)
                app.state.domain_intake = domain_intake
                analysis = configure_domain_analysis(domain_intake, materials, settings)
                app.state.domain_analysis = analysis
                processing = configure_intake_processing(analysis)
                app.state.domain_intake_processing = processing
                instances = configure_instances(analysis)
                app.state.domain_instances = instances
                app.state.receipts = RequestReceipts(
                    {
                        (
                            "product.record_usage_confirmation",
                            "account",
                        ): app.state.usage.read_receipt,
                        (SAVE_ACTION, "account"): domain.read_receipt,
                        (CONFIRM_PATH_ACTION, "domain"): domain.read_path_receipt,
                        (RECEIVE_MATERIAL, "domain"): materials.read_receipt,
                        (RECEIVE_MATERIAL, "material_import"): materials.read_receipt,
                        (CONVERSE, "material_import"): assistant.receipt,
                        (DECIDE, "material_import"): adoptions.receipt,
                        (SUBMIT_INTAKE, "material_import"): intake.receipt,
                        (EXTRACT, "domain"): analysis.receipt,
                        (CLASSIFY, "domain"): analysis.receipt,
                        (PROCESS_INTAKE, "domain"): processing.receipt,
                        (SAVE_INSTANCE, "domain"): instances.receipt,
                        (DELETE_MATERIAL, "material_import"): deletion.receipt,
                        (CHAPTER_ACTION, "textbook"): chapters.receipt,
                        (MANAGE_CLAIM, "domain"): claims.receipt,
                        (MANAGE_ACTIVITY, "activity_config"): configs.receipt,
                        (SAVE_TARGET, "textbook"): targets.receipt,
                        (CHECK_COURSE, "textbook"): checks.receipt,
                        (CONFIRM_COURSE, "textbook"): applications.receipt,
                        (OPEN_SPACE, "account"): spaces.receipt,
                        (CONTROL_ACTIVITY, "learning_space"): conversation.receipt,
                        (HANDLE_INPUT, "learning_space"): turns.requests.receipt,
                        (SUBMIT_ANSWER, "learning_space"): turns.requests.receipt,
                        (PREPARE_DETECTION, "learning_space"): turns.requests.receipt,
                    }
                )
                app.state.realtime = hub

                async def refresh(event_id: UUID) -> None:
                    change = await resolve_view_change(engine, event_id, routes)
                    if change:
                        await hub.notify(change.kind, change.resource_id, change.views)

                messaging = None
                if "M1_NATS_ADDRESS" in os.environ:
                    messaging = MessagingSettings.from_environment()
                notices = ViewNotices(messaging, refresh, hub.resync)
                app.state.view_notices = notices
                LOGGER.info(
                    "API 已启动，数据库版本及共享文件目录检查通过",
                    extra={"action": "api_started", "outcome": "success"},
                )
                async with notices.listen():
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
    app.include_router(usage_router)
    app.include_router(domain_router)
    app.include_router(materials_router)
    app.include_router(evaluation_router)
    app.include_router(activity_router)
    app.include_router(target_router)
    app.include_router(courses_router)
    app.include_router(conversation_router)

    app.include_router(receipts_router)
    app.include_router(realtime_router)
    app.add_middleware(RequestBodyLimit)
    for error_type in (
        RequestError,
        RequestConflict,
        IntegrityError,
        RequestValidationError,
        SQLAlchemyError,
        StarletteHTTPException,
        Exception,
    ):
        app.add_exception_handler(error_type, api_error)

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
        **websocket_options(),
    )
