"""E01-17 测试专用应用。接通真实会话、确认事务、收据和提交后的提示。"""

import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from deermind.abstractions.events import Ref
from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.api.realtime import Command, CommandResult, Realtime, Resource
from deermind.foundation.system.public.errors import RequestError
from deermind.product.public.authentication import AuthError, SessionView
from deermind.product.public.errors import RequestConflict
from deermind.product.public.usage import ConfirmUsageRequest, UsageService
from fastapi import FastAPI
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONFIRM_ACTION = "test.confirm"
PAD_ACTION = "test.pad"
RECEIPT_ACTION = "product.record_usage_confirmation"
RESOURCE_KIND = "account"
VIEWS = frozenset({"usage"})


def environment(database: URL, root: Path, *origins: str) -> dict[str, str]:
    """只使用随机测试库和测试提示主题，避免两个用例互相收到提示。"""
    assert database.database is not None and database.database.startswith("dm_e0104_test_")
    return {
        "M1_DB_HOST": str(database.host),
        "M1_DB_PORT": str(database.port),
        "M1_DB_NAME": database.database,
        "M1_DB_USER": "deermind_app",
        "M1_DB_PASSWORD": str(database.password),
        "M1_FILES_ROOT": str(root),
        "M1_FILES_BACKEND": "local",
        "M1_TEMPORAL_ADDRESS": "127.0.0.1:1",
        "M1_TEMPORAL_NAMESPACE": "browser-test",
        "M1_TASK_QUEUE": "unused",
        "M1_AUTH_LOCAL_HTTP": "true",
        "M1_AUTH_ORIGINS": ",".join(origins),
        "M1_AUTH_TRUSTED_PROXIES": "",
        "M1_NATS_ADDRESS": os.environ["M1_TEST_NATS_ADDRESS"],
        "M1_NATS_DEPLOYMENT": "ws-test-" + uuid4().hex[:12],
        "M1_NATS_USER": "maintenance",
        "M1_NATS_PASSWORD": os.environ["M1_TEST_NATS_PASSWORD"],
    }


async def authorize(session: SessionView, resource: Resource, views: frozenset[str]) -> bool:
    """只允许合成学生本人的确认范围。"""
    return (
        resource.kind == RESOURCE_KIND
        and resource.id == str(session.account.account_id)
        and session.account.role == "student"
        and views <= VIEWS
    )


class RealtimeFixture:
    """把隔离命令映射到真实 Product 确认处理器。"""

    def __init__(self) -> None:
        self.drop_next_receipt = False
        self.suppress_next_notice = False
        self.event_ids: dict[str, UUID] = {}
        self.app: FastAPI = create_app(
            realtime=Realtime(
                commands={CONFIRM_ACTION: self.confirm, PAD_ACTION: self.pad},
                views={RESOURCE_KIND: VIEWS},
                authorize=authorize,
            ),
            view_routes={("UsageConfirmationRecorded", RESOURCE_KIND): VIEWS},
        )

    async def confirm(self, session: SessionView, command: Command) -> CommandResult:
        """先提交真实确认，再读取提交的事件并发布提示。"""
        body = ConfirmUsageRequest.model_validate_json(
            json.dumps({**command.payload, "request_id": command.request_id})
        )
        if str(body.confirmation.student_id) != command.resource.id:
            raise AuthError(404, "not_found", "确认范围不匹配。")
        usage: UsageService = self.app.state.usage
        try:
            result = await usage.confirm(session, body)
        except RequestConflict as error:
            raise RequestError(409, "request_conflict", "请求身份或内容冲突。") from error
        engine: AsyncEngine = self.app.state.database
        async with engine.connect() as connection:
            event_id = await connection.scalar(
                text(
                    "SELECT event_id FROM runtime.events "
                    "WHERE event_type='UsageConfirmationRecorded' AND correlation_id=:ref"
                ),
                {"ref": result.request_ref},
            )
        assert isinstance(event_id, UUID)
        self.event_ids[command.request_id] = event_id
        if self.suppress_next_notice:
            self.suppress_next_notice = False
        else:
            await self.app.state.view_notices.publish(event_id)
        return CommandResult(
            state="completed",
            owner_receipt_ref=str(result.request_ref),
            result_refs=[result.result.confirmation_ref],
        )

    async def pad(self, session: SessionView, command: Command) -> CommandResult:
        """向非读取连接发出大回执，触发真实 TCP 背压。"""
        return CommandResult(
            state="completed",
            owner_receipt_ref=command.request_id,
            result_refs=[Ref(owner="test", type="padding", id="x" * 60000)],
        )

    def transport(self) -> ASGIApp:
        """在测试传输上只丢弃一条已提交的回执，并主动断线。"""

        async def intercept(scope: Scope, receive: Receive, send: Send) -> None:
            async def observe(message: Message) -> None:
                if (
                    self.drop_next_receipt
                    and message["type"] == "websocket.send"
                    and json.loads(message.get("text") or "{}").get("type") == "receipt"
                ):
                    self.drop_next_receipt = False
                    await send({"type": "websocket.close", "code": 1012})
                    return
                await send(message)

            await self.app(scope, receive, observe if scope["type"] == "websocket" else send)

        return intercept
