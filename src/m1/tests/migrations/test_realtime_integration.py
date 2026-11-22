"""真实 API、WebSocket、PostgreSQL 与 Core NATS 的隔离接线测试。"""

import asyncio
import json
import socket
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import uvicorn
from deermind.entrypoints.api.app import websocket_options
from deermind.entrypoints.maintenance.database import upgrade
from deermind.product.public.authentication import SessionView
from deermind.product.public.usage import UsageView
from httpx2 import AsyncClient
from pydantic import JsonValue, TypeAdapter
from realtime_fixture import (
    CONFIRM_ACTION,
    PAD_ACTION,
    RECEIPT_ACTION,
    RESOURCE_KIND,
    RealtimeFixture,
    environment,
)
from sqlalchemy import text
from test_account_usage import PASSWORD
from test_database import DatabaseTestCase
from usage_browser import seed
from websockets import Origin, Subprotocol
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

OBJECT = TypeAdapter(dict[str, JsonValue])
PROTOCOL = "deermind.v1"
FRAME_TIMEOUT = 10


@dataclass(frozen=True)
class Endpoint:
    origin: str
    listener: socket.socket

    @property
    def websocket(self) -> str:
        return "ws" + self.origin[4:] + "/ws"


def endpoint(listener: socket.socket) -> Endpoint:
    """先保留本机端口，避免并行测试争用同一个地址。"""
    listener.bind(("127.0.0.1", 0))
    return Endpoint(f"http://127.0.0.1:{listener.getsockname()[1]}", listener)


@asynccontextmanager
async def serve(fixture: RealtimeFixture, address: Endpoint) -> AsyncGenerator[None]:
    """使用实际 Uvicorn 后端测试重组消息与 TCP 背压。"""
    config = uvicorn.Config(
        fixture.transport(),
        proxy_headers=False,
        log_level="warning",
        timeout_graceful_shutdown=3,
        **websocket_options(),
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(sockets=[address.listener]))
    try:
        async with asyncio.timeout(30):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Realtime test server stopped before startup")
                await asyncio.sleep(0.05)
            await fixture.app.state.view_notices.ready.wait()
        yield
    finally:
        server.should_exit = True
        async with asyncio.timeout(10):
            await task


async def send(peer: ClientConnection, frame: dict[str, JsonValue]) -> None:
    await peer.send(json.dumps(frame))


async def receive(peer: ClientConnection, kind: str) -> dict[str, JsonValue]:
    """在保活帧和合并通知中定位预期业务帧。"""
    async with asyncio.timeout(FRAME_TIMEOUT):
        while True:
            frame = OBJECT.validate_json(await peer.recv())
            if frame["type"] == "ping":
                await send(peer, {"type": "pong", "frame_id": frame["frame_id"]})
            elif frame["type"] == kind:
                return frame
            elif frame["type"] not in {"changed", "resync_required"}:
                raise AssertionError(f"Expected {kind}, got frame {frame['type']}")


async def receive_update(peer: ClientConnection) -> dict[str, JsonValue]:
    """通知与请求回执可按两个合法顺序抵达。"""
    first = OBJECT.validate_json(await asyncio.wait_for(peer.recv(), FRAME_TIMEOUT))
    if first["type"] == "changed":
        await receive(peer, "receipt")
        return first
    if first["type"] == "receipt":
        return await receive(peer, "changed")
    raise AssertionError(f"Unexpected frame while waiting for update: {first['type']}")


async def hello(peer: ClientConnection, session: SessionView) -> None:
    await send(
        peer,
        {
            "type": "hello",
            "session_id": str(session.session_id),
            "csrf_token": session.csrf_token,
        },
    )
    await receive(peer, "ready")


def account(session: SessionView) -> dict[str, JsonValue]:
    return {"kind": RESOURCE_KIND, "id": str(session.account.account_id)}


def watch(resource: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        "type": "watch",
        "frame_id": str(uuid4()),
        "watch_id": str(uuid4()),
        "resource": resource,
        "views": ["usage"],
    }


def command(
    session: SessionView, view: UsageView, *, request_id: str, decision: str = "declined"
) -> dict[str, JsonValue]:
    return {
        "type": "command",
        "frame_id": str(uuid4()),
        "request_id": request_id,
        "action": CONFIRM_ACTION,
        "resource": account(session),
        "payload": {
            "expected_revision": view.revision,
            "confirmation": {
                "student_id": str(session.account.account_id),
                "kind": "student_assent",
                "decision": decision,
                "notice_ref": view.notice_ref.model_dump(mode="json"),
                "source_ref": view.source_ref.model_dump(mode="json"),
            },
        },
    }


async def login(client: AsyncClient, origin: str) -> SessionView:
    response = await client.post(
        origin + "/api/m1/auth/sign-in",
        headers={"Origin": origin},
        json={"login_identifier": "student", "password": PASSWORD},
    )
    response.raise_for_status()
    response = await client.get(origin + "/api/m1/auth/session")
    return SessionView.model_validate_json(response.raise_for_status().content)


def session_headers(session: SessionView) -> dict[str, str]:
    return {
        "X-Expected-Session": str(session.session_id),
        "X-CSRF-Token": session.csrf_token,
    }


async def current_usage(client: AsyncClient, origin: str, session: SessionView) -> UsageView:
    response = await client.get(
        origin + "/api/m1/usage-conditions", headers=session_headers(session)
    )
    return UsageView.model_validate_json(response.raise_for_status().content)


async def receipt(
    client: AsyncClient, origin: str, session: SessionView, request_id: str
) -> dict[str, JsonValue]:
    response = await client.get(
        origin + "/api/m1/requests/receipt",
        headers=session_headers(session),
        params={
            "action": RECEIPT_ACTION,
            "resource_kind": RESOURCE_KIND,
            "resource_id": str(session.account.account_id),
            "request_id": request_id,
        },
    )
    return OBJECT.validate_json(response.raise_for_status().content)


def connection(address: Endpoint, client: AsyncClient, *, origin: str | None = None) -> connect:
    token = client.cookies.get("dm_session_local")
    return connect(
        address.websocket,
        origin=Origin(origin or address.origin),
        additional_headers={"Cookie": f"dm_session_local={token}"} if token else None,
        subprotocols=[Subprotocol(PROTOCOL)],
        compression=None,
        open_timeout=FRAME_TIMEOUT,
        close_timeout=2,
    )


class RealtimeIntegrationTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        asyncio.run(seed(self))
        self.confirmations_before = self.event_count()

    @asynccontextmanager
    async def isolated(self) -> AsyncGenerator[tuple[Endpoint, Endpoint, RealtimeFixture]]:
        """一次试验使用一套真实存储、两个独立 API 和唯一通知主题。"""
        with tempfile.TemporaryDirectory() as root, socket.socket() as a, socket.socket() as b:
            first, second = endpoint(a), endpoint(b)
            with patch.dict(
                "os.environ", environment(self.app, Path(root), first.origin, second.origin)
            ):
                yield first, second, RealtimeFixture()

    def test_authorization_and_fragment_budget(self) -> None:
        asyncio.run(self.authorization_and_fragment_budget())

    async def authorization_and_fragment_budget(self) -> None:
        async with self.isolated() as (address, _, fixture), serve(fixture, address):
            async with AsyncClient(trust_env=False) as client:
                with self.assertRaises(InvalidStatus):
                    async with connection(address, client):
                        self.fail("Missing Cookie was accepted")
                session = await login(client, address.origin)
                with self.assertRaises(InvalidStatus):
                    async with connection(address, client, origin="https://invalid.example"):
                        self.fail("Foreign Origin was accepted")
                async with connection(address, client) as peer:
                    await send(
                        peer,
                        {
                            "type": "hello",
                            "session_id": str(session.session_id),
                            "csrf_token": "invalid-token",
                        },
                    )
                    async with asyncio.timeout(FRAME_TIMEOUT):
                        with self.assertRaises(ConnectionClosed):
                            while True:
                                await peer.recv()
                async with connection(address, client) as peer:
                    await hello(peer, session)
                    await send(peer, watch({"kind": RESOURCE_KIND, "id": str(uuid4())}))
                    self.assertEqual((await receive(peer, "error"))["acceptance"], "not_accepted")
                    await peer.send([" " * 32768, " " * 32769])
                    with self.assertRaises(ConnectionClosed) as oversized:
                        await asyncio.wait_for(peer.recv(), FRAME_TIMEOUT)
                    self.assertIsNotNone(oversized.exception.rcvd)
                    assert oversized.exception.rcvd is not None
                    self.assertEqual(oversized.exception.rcvd.code, 1009)
                async with connection(address, client) as peer:
                    await hello(peer, session)
                    response = await client.post(
                        address.origin + "/api/m1/auth/sign-out",
                        headers={"Origin": address.origin, **session_headers(session)},
                    )
                    response.raise_for_status()
                    await send(peer, watch(account(session)))
                    async with asyncio.timeout(FRAME_TIMEOUT):
                        with self.assertRaises(ConnectionClosed):
                            while True:
                                await peer.recv()
        self.assertEqual(self.confirmation_count(), 0)

    def test_lost_receipt_recovery_and_exact_replay(self) -> None:
        asyncio.run(self.lost_receipt_recovery_and_exact_replay())

    async def lost_receipt_recovery_and_exact_replay(self) -> None:
        async with self.isolated() as (first, second, fixture):
            async with AsyncClient(trust_env=False) as client:
                request_id = str(uuid4())
                async with serve(fixture, first):
                    session = await login(client, first.origin)
                    view = await current_usage(client, first.origin, session)
                    before = await receipt(client, first.origin, session, request_id)
                    self.assertEqual(before["receipt_state"], "not_found")
                    fixture.drop_next_receipt = True
                    async with connection(first, client) as peer:
                        await hello(peer, session)
                        await send(peer, command(session, view, request_id=request_id))
                        with self.assertRaises(ConnectionClosed):
                            await asyncio.wait_for(peer.recv(), FRAME_TIMEOUT)
                    self.assertIn(request_id, fixture.event_ids)
                async with serve(RealtimeFixture(), second):
                    async with connection(second, client) as peer:
                        await hello(peer, session)
                        await send(peer, watch(account(session)))
                        await receive(peer, "watch_ready")
                        saved = await receipt(client, second.origin, session, request_id)
                        self.assertEqual(saved["receipt_state"], "completed")
                        await send(peer, command(session, view, request_id=request_id))
                        replayed = await receive(peer, "receipt")
                        self.assertEqual(replayed["owner_receipt_ref"], saved["receipt_ref"])
                        await send(
                            peer, command(session, view, request_id=request_id, decision="accepted")
                        )
                        refused = await receive(peer, "error")
                        self.assertEqual(refused["acceptance"], "not_accepted")
        self.assertEqual(self.confirmation_count(), 1)

    def test_fanout_and_independent_reads_cover_missing_notices(self) -> None:
        asyncio.run(self.fanout_and_independent_reads_cover_missing_notices())

    async def fanout_and_independent_reads_cover_missing_notices(self) -> None:
        async with self.isolated() as (first, second, fixture):
            async with serve(fixture, first), serve(RealtimeFixture(), second):
                async with AsyncClient(trust_env=False) as client:
                    session = await login(client, first.origin)
                    view = await current_usage(client, first.origin, session)
                    async with connection(first, client) as a, connection(second, client) as b:
                        for peer in (a, b):
                            await hello(peer, session)
                            await send(peer, watch(account(session)))
                            await receive(peer, "watch_ready")
                        # 故意丢掉一次刷新提示。真实 HTTP 仍能补读提交结果。
                        fixture.suppress_next_notice = True
                        missing_id = str(uuid4())
                        await send(a, command(session, view, request_id=missing_id))
                        await receive(a, "receipt")
                        with self.assertRaises(TimeoutError):
                            await asyncio.wait_for(b.recv(), 0.25)
                        saved = await receipt(client, second.origin, session, missing_id)
                        self.assertEqual(saved["receipt_state"], "completed")
                        updated = await current_usage(client, second.origin, session)
                        self.assertGreater(updated.revision, view.revision)

                        notified_id = str(uuid4())
                        await send(
                            a,
                            command(session, updated, request_id=notified_id, decision="accepted"),
                        )
                        received = await asyncio.gather(receive_update(a), receive(b, "changed"))
                        for hint in received:
                            self.assertEqual(hint["resource"], account(session))
                            self.assertEqual(hint["views"], ["usage"])
                            self.assertFalse({"payload", "result_refs"} & hint.keys())
                        event_id = fixture.event_ids[notified_id]
                        self.assertTrue(await fixture.app.state.view_notices.publish(event_id))
                        duplicate = await receive(b, "changed")
                        self.assertEqual(duplicate["resource"], account(session))
                        self.assertEqual(duplicate["views"], ["usage"])
        self.assertEqual(self.confirmation_count(), 2)

    def test_nonreading_connection_does_not_block_healthy_watcher(self) -> None:
        asyncio.run(self.nonreading_connection_does_not_block_healthy_watcher())

    async def nonreading_connection_does_not_block_healthy_watcher(self) -> None:
        async with self.isolated() as (address, _, fixture):
            # 降低接受连接继承的发送缓冲，让本机 TCP 也可稳定产生背压。
            address.listener.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            async with serve(fixture, address), AsyncClient(trust_env=False) as client:
                session = await login(client, address.origin)
                view = await current_usage(client, address.origin, session)
                async with connection(address, client) as slow, connection(address, client) as good:
                    await hello(slow, session)
                    await hello(good, session)
                    await send(good, watch(account(session)))
                    await receive(good, "watch_ready")
                    transport = slow.transport
                    peer_socket = transport.get_extra_info("socket")
                    peer_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
                    transport.pause_reading()
                    try:
                        async with asyncio.timeout(FRAME_TIMEOUT):
                            for _ in range(24):
                                identifier = str(uuid4())
                                await send(
                                    slow,
                                    {
                                        "type": "command",
                                        "frame_id": identifier,
                                        "request_id": identifier,
                                        "action": PAD_ACTION,
                                        "resource": account(session),
                                        "payload": {},
                                    },
                                )
                        key = str(uuid4())
                        await send(good, command(session, view, request_id=key))
                        await receive(good, "receipt")
                        self.assertEqual(
                            (await receipt(client, address.origin, session, key))["receipt_state"],
                            "completed",
                        )
                        # 先确认服务端已隔离慢连接。TCP 关闭握手可能仍等待对端恢复读取。
                        async with asyncio.timeout(18):
                            while len(fixture.app.state.realtime.connections) != 1:
                                await asyncio.sleep(0.05)
                        await send(
                            good,
                            {"type": "ping", "frame_id": str(uuid4())},
                        )
                        await receive(good, "pong")
                    finally:
                        if not transport.is_closing():
                            transport.abort()
        self.assertEqual(self.confirmation_count(), 1)

    def confirmation_count(self) -> int:
        return self.event_count() - self.confirmations_before

    def event_count(self) -> int:
        """断言写入次数，以实际事件为准。"""
        with self.engine.connect() as connection:
            return int(
                connection.scalar(
                    text("SELECT count(*) FROM runtime.events WHERE event_type=:kind"),
                    {"kind": "UsageConfirmationRecorded"},
                )
                or 0
            )
