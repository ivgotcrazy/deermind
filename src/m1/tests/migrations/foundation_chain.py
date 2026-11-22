"""E01-18 合成命令接真实受理、JetStream、Temporal 与 R04。"""

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.bootstrap.executions import limits
from deermind.bootstrap.settings import Settings
from deermind.bootstrap.temporal import connect_temporal
from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.api.auth import access
from deermind.entrypoints.api.realtime import Command, CommandResult, Realtime, Resource
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.delivery.bridge import run_bridge
from deermind.foundation.system.delivery.contracts import (
    Subscription,
    SubscriptionRegistry,
    specifications,
)
from deermind.foundation.system.delivery.outbox import Outbox
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import Caller
from deermind.foundation.system.executions.relay import run_relay
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.foundation.system.requests import RequestReceipts
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.nats.connection import JetStream, MessagingSettings, connect
from deermind.infrastructure.temporal.executions import Transport
from deermind.product.accounts.save import canonical_actor
from deermind.product.persistence.receipts import claim_request, complete_request
from deermind.product.public.authentication import SessionView
from deermind.product.public.usage import ConfirmationResult
from execution_worker import lock_owner
from fastapi import FastAPI, Header, Request
from foundation_chain_data import (
    ACTION,
    ENTRY_NAME,
    INPUT_EVENT,
    INPUT_REGISTRATION,
    RESOURCE_KIND,
    RESULT_EVENT,
    VIEW,
    InputPayload,
    account_ref,
    account_sequence,
    input_ref,
    registry,
)
from nats.js.api import StreamConfig
from nats.js.errors import NotFoundError
from pydantic import SecretStr
from realtime_fixture import RealtimeFixture, environment
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from test_database import DatabaseTestCase
from usage_browser import seed

type ChainReceipt = ReceiptView[ConfirmationResult]


async def authorize(session: SessionView, resource: Resource, views: frozenset[str]) -> bool:
    return (
        resource.kind == RESOURCE_KIND
        and resource.id == str(session.account.account_id)
        and session.account.role == "student"
        and views <= {VIEW}
    )


async def durable_counts(connection: AsyncConnection) -> dict[str, int]:
    """用测试专库的持久计数比较拒绝前后，包含派发和后台工作。"""
    row = (
        (
            await connection.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM product.command_receipt "
                    "WHERE action=:action) AS receipts,"
                    "(SELECT count(*) FROM runtime.events "
                    "WHERE event_type=:event) AS input_facts,"
                    "(SELECT count(*) FROM runtime.executions "
                    "WHERE entry_ref=:entry) AS executions,"
                    "(SELECT count(*) FROM runtime.handoffs "
                    "WHERE kind IN ('publish','start')) AS handoffs"
                ),
                {"action": ACTION, "event": INPUT_EVENT, "entry": ENTRY_NAME},
            )
        )
        .mappings()
        .one()
    )
    return {key: int(value) for key, value in row.items()}


class ChainFixture(RealtimeFixture):
    """复用 E01-17 的只丢回执传输夹具，绑定一套独立运行资源。"""

    def __init__(
        self, database: DatabaseTestCase, scope: UUID, files_root: Path, origin: str
    ) -> None:
        self.database = database
        self.scope = scope
        self.drop_next_receipt = False
        self.restart_worker = False
        self.recovery_request: str | None = None
        self.busy = False
        self.denied_requests: dict[str, dict[str, int]] = {}
        self.env = environment(database.app, files_root, origin)
        self.deployment = "chain-" + uuid4().hex[:12]
        self.env.update(
            M1_NATS_DEPLOYMENT=self.deployment,
            M1_TASK_QUEUE="dm." + self.deployment,
            M1_AUTH_LOCAL_HTTP=str(origin.startswith("http:")).lower(),
            M1_TEMPORAL_ADDRESS=os.environ["M1_TEST_TEMPORAL_ADDRESS"],
            M1_TEMPORAL_NAMESPACE=os.environ["M1_TEST_TEMPORAL_NAMESPACE"],
        )
        self.settings = Settings(
            files_root=files_root,
            files_backend="local",
            temporal_address=self.env["M1_TEMPORAL_ADDRESS"],
            temporal_namespace=self.env["M1_TEMPORAL_NAMESPACE"],
            task_queue=self.env["M1_TASK_QUEUE"],
        )
        self.entries = registry(scope, self.settings.task_queue)
        self.subscriber = Subscription(
            "foundation_chain",
            "1",
            frozenset({INPUT_EVENT}),
            frozenset({RESOURCE_KIND}),
            self.consume,
        )
        self.subscriptions = SubscriptionRegistry([self.subscriber])
        self.events = EventStore(
            [INPUT_REGISTRATION], arrange_delivery=Outbox(self.subscriptions).arrange
        )
        self.app = create_app(
            realtime=Realtime(
                commands={ACTION: self.submit},
                views={RESOURCE_KIND: frozenset({VIEW})},
                authorize=authorize,
            ),
            view_routes={(RESULT_EVENT, RESOURCE_KIND): frozenset({VIEW})},
        )
        self.install_lifespan()

        @self.app.post("/api/m1/test/foundation-chain/control")
        async def control(
            request: Request,
            controls: dict[str, bool],
        ) -> dict[str, bool]:
            access(request, writing=True)
            if not controls.keys() <= {"busy", "drop_next_receipt", "restart_worker"}:
                raise RequestError(400, "invalid_request", "未知测试开关。")
            self.busy = controls.get("busy", self.busy)
            self.drop_next_receipt = controls.get("drop_next_receipt", self.drop_next_receipt)
            self.restart_worker = controls.get("restart_worker", self.restart_worker)
            return {
                "busy": self.busy,
                "drop_next_receipt": self.drop_next_receipt,
                "restart_worker": self.restart_worker,
            }

        @self.app.get("/api/m1/test/foundation-chain/results/{execution_id}")
        async def saved_result(
            request: Request,
            execution_id: UUID,
            expected: str | None = Header(default=None, alias="X-Expected-Session"),
        ) -> dict[str, str]:
            auth, config = access(request)
            if expected is None:
                raise RequestError(403, "forbidden", "请先刷新登录状态。")
            session = await auth.session(request.cookies.get(config.cookie_name), expected)
            if session.account.account_id != self.scope or session.account.role != "student":
                raise RequestError(404, "not_found", "找不到测试结果。")
            engine: AsyncEngine = self.app.state.database
            async with engine.connect() as connection:
                row = (
                    (
                        await connection.execute(
                            text(
                                "SELECT result.* FROM product.foundation_chain_results AS result "
                                "JOIN runtime.executions AS execution USING(execution_id) "
                                "WHERE execution_id=:id AND execution.scope_id=:scope "
                                "AND execution.entry_ref=:entry AND execution.state='completed'"
                            ),
                            {"id": execution_id, "scope": self.scope, "entry": ENTRY_NAME},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            if row is None:
                raise RequestError(404, "not_found", "找不到测试结果。")
            return {key: str(row[key]) for key in row.keys()}

    def install_lifespan(self) -> None:
        """启动正常底座后，为隔离应用追加收据登记和可靠交接循环。"""
        startup = self.app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
            async with startup(app), self.messaging() as nats:
                app.state.receipts = RequestReceipts({(ACTION, RESOURCE_KIND): self.read_receipt})
                engine: AsyncEngine = app.state.database
                temporal = await connect_temporal(self.settings, engine)
                execution_limits = limits()
                stopped = asyncio.Event()
                async with asyncio.TaskGroup() as tasks:
                    tasks.create_task(run_bridge(engine, nats, self.subscriptions, stopped))
                    tasks.create_task(
                        run_relay(
                            engine, self.entries, Transport(temporal, execution_limits), stopped
                        )
                    )
                    try:
                        yield
                    finally:
                        stopped.set()

        self.app.router.lifespan_context = lifespan

    @asynccontextmanager
    async def messaging(self) -> AsyncGenerator[JetStream]:
        settings = MessagingSettings(
            address=self.env["M1_NATS_ADDRESS"],
            deployment=self.deployment,
            user=self.env["M1_NATS_USER"],
            password=SecretStr(self.env["M1_NATS_PASSWORD"]),
        )
        async with connect(settings) as transport:
            default_config = transport.stream_config

            def small_stream(*, failure: bool) -> StreamConfig:
                return replace(default_config(failure=failure), max_bytes=1024 * 1024)

            with patch.object(transport, "stream_config", side_effect=small_stream):
                try:
                    await transport.initialize(specifications(self.subscriptions))
                    yield transport
                finally:
                    for stream in (settings.stream, settings.failures):
                        try:
                            await transport.js.delete_stream(stream)
                        except NotFoundError:
                            pass

    async def submit(self, session: SessionView, command: Command) -> CommandResult:
        """固定同一请求身份，输入事实、收据与发布安排共同提交。"""
        account_id = session.account.account_id
        if account_id != self.scope:
            raise RequestError(404, "not_found", "找不到测试资源。")
        try:
            request_id = str(UUID(command.request_id))
            if command.payload.keys() != {"text"}:
                raise ValueError("Unexpected fixture command fields")
            payload = InputPayload.model_validate({**command.payload, "records": []})
        except ValueError as error:
            raise RequestError(400, "invalid_request", "请求格式不正确。") from error
        account = account_ref(account_id)
        engine: AsyncEngine = self.app.state.database
        async with engine.begin() as connection:
            before_refusal = await durable_counts(connection) if self.busy else None
            receipt = await claim_request(
                connection,
                principal_id=canonical_actor(account),
                action=ACTION,
                scope_id=str(account_id),
                request_id=request_id,
                normalized_input=command.payload,
            )
            if receipt.result_ref is None:
                if before_refusal is not None:
                    self.denied_requests[request_id] = before_refusal
                    raise RequestError(429, "resource_busy", "资源暂不可用，请稍后重新提交。")
                if self.restart_worker:
                    self.recovery_request = request_id
                    self.restart_worker = False
                scope = (RESOURCE_KIND, account_id)
                await lock_owner(connection, *scope)
                identity = uuid4()
                await self.events.append(
                    connection,
                    ProducerAccess("product", account, frozenset({scope})),
                    [
                        EventDraft(
                            identity,
                            INPUT_EVENT,
                            1,
                            *scope,
                            account,
                            payload.model_dump(mode="json"),
                            request_id,
                        )
                    ],
                    commit_id=uuid4(),
                    correlation_id=receipt.request_ref,
                    expected_seq={scope: await account_sequence(connection, account_id)},
                )
                await complete_request(connection, receipt, input_ref(identity))
        view = await self.read_receipt(
            account_id,
            session.session_id,
            ReceiptQuery(
                action=ACTION,
                resource_kind=RESOURCE_KIND,
                resource_id=account_id,
                request_id=request_id,
            ),
        )
        return CommandResult(
            state="completed" if view.receipt_state == "completed" else "accepted",
            owner_receipt_ref=str(receipt.request_ref),
            execution_ref=str(view.execution_ref) if view.execution_ref else None,
            result_refs=view.result_refs,
        )

    async def consume(self, connection: AsyncConnection, event: EventNotice) -> Acceptance:
        """可靠接收的收据与启动安排同事务；Temporal 执行另走 Relay。"""
        if event.scope_id != self.scope:
            raise PermissionError("Unexpected fixture scope")
        scope = (RESOURCE_KIND, event.scope_id)
        anchor = input_ref(event.event_id)
        execution = await store.accept(
            connection,
            self.entries,
            Caller(
                account_ref(event.scope_id),
                "product",
                frozenset({scope}),
                frozenset({"accept", "read", "execute", "commit"}),
            ),
            entry_name=ENTRY_NAME,
            scope_kind=scope[0],
            scope_id=scope[1],
            acceptance_key=str(event.event_id),
            input_ref=anchor,
            seconds=240,
            basis_refs=[anchor],
        )
        return Acceptance(
            disposition="accepted",
            arrangement_refs=[
                Ref(owner="runtime", type="execution", id=str(execution.execution_id))
            ],
        )

    async def read_receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ChainReceipt:
        """只读原请求的合成工作身份、已发布结果引用和执行状态。"""
        if principal != self.scope or query.resource_id != principal:
            raise RequestError(404, "not_found", "找不到测试请求。")
        engine: AsyncEngine = self.app.state.database
        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT receipt.request_ref,execution.execution_id,execution.state,"
                            " execution.result_ref,result.source_event_id"
                            " FROM product.command_receipt AS receipt"
                            " LEFT JOIN runtime.executions AS execution"
                            " ON execution.entry_ref=:entry"
                            " AND execution.scope_id=:scope"
                            " AND execution.acceptance_key=receipt.result_ref ->> 'id'"
                            " LEFT JOIN product.foundation_chain_results AS result"
                            " ON result.execution_id=execution.execution_id"
                            " WHERE receipt.principal_id=:principal"
                            " AND receipt.scope_id=:scope_text"
                            " AND receipt.action=:action AND receipt.request_id=:request_id"
                        ),
                        {
                            "entry": ENTRY_NAME,
                            "scope": principal,
                            "scope_text": str(principal),
                            "principal": canonical_actor(account_ref(principal)),
                            "action": ACTION,
                            "request_id": query.request_id,
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None and query.request_id in self.denied_requests:
                facts = await connection.scalar(
                    text(
                        "SELECT count(*) FROM runtime.events WHERE scope_kind='account' "
                        "AND scope_id=:scope AND event_type=:event AND source_request_id=:request"
                    ),
                    {"scope": principal, "event": INPUT_EVENT, "request": query.request_id},
                )
                assert facts == 0
                counts = await durable_counts(connection)
                before_refusal = self.denied_requests.pop(query.request_id)
                assert counts == before_refusal
                print(
                    f"E01-18 resource refusal {query.request_id}: "
                    f"before={before_refusal} after={counts}; logical request absent",
                    flush=True,
                )
        if row is None:
            return ReceiptView[ConfirmationResult](receipt_state="not_found")
        completed = row["state"] == "completed"
        if completed and row["source_event_id"] is None:
            raise RuntimeError("A completed execution has no owner projection")
        return ReceiptView[ConfirmationResult](
            receipt_state="completed" if completed else "accepted",
            receipt_ref=row["request_ref"],
            execution_ref=row["execution_id"],
            execution_state=row["state"],
            result_refs=[Ref.model_validate(row["result_ref"])] if completed else [],
        )


async def seed_scope(database: DatabaseTestCase) -> UUID:
    """仅在现有随机测试库安装本轮所有者投影并创建合成账号。"""
    await seed(database)
    engine = application_engine(database.migrator)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "CREATE TABLE product.foundation_chain_results ("
                    "execution_id uuid PRIMARY KEY, input_event_id uuid NOT NULL UNIQUE, "
                    "sha256 text NOT NULL, source_event_id uuid NOT NULL UNIQUE)"
                )
            )
            await connection.execute(
                text("GRANT SELECT,INSERT ON product.foundation_chain_results TO deermind_app")
            )
            scope = await connection.scalar(
                text("SELECT account_id FROM product.accounts WHERE login_identifier='student'")
            )
        assert isinstance(scope, UUID)
        return scope
    finally:
        await engine.dispose()


def migrated_fixture(database: DatabaseTestCase) -> UUID:
    upgrade(database.migrator)
    return asyncio.run(seed_scope(database))
