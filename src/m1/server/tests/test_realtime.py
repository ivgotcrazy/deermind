"""WebSocket 授权、刷新提示及缓冲边界。"""

import asyncio
import json
import unittest
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from deermind.entrypoints.api import realtime
from deermind.entrypoints.api.realtime_protocol import Error, Heartbeat, Watch
from deermind.foundation.system.public.errors import ErrorDetail, RequestError
from deermind.product.public.auth_config import AuthConfig
from deermind.product.public.authentication import AccountView, AuthError, SessionView
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel, ValidationError
from starlette.types import Message

_SITE = "http://localhost"
_COOKIE = "dm_session_local=test-login"


class _Auth:
    def __init__(self) -> None:
        self.view = SessionView(
            account=AccountView(
                account_id=uuid4(), display_name="学生", role="student", usage_gaps=[]
            ),
            session_id=uuid4(),
            csrf_token="test-csrf",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        self.revoked = False

    async def session(self, token: str | None, expected: str | None = None) -> SessionView:
        if token != "test-login" or self.revoked:
            raise AuthError(401, "unauthenticated", "登录已失效。")
        if expected is not None and expected != str(self.view.session_id):
            raise AuthError(409, "session_changed", "登录已变更。")
        return self.view


class _Peer:
    def __init__(
        self,
        app: FastAPI,
        headers: list[tuple[bytes, bytes]],
        protocols: list[str],
        before_send: Callable[[Message], Awaitable[None]] | None,
    ) -> None:
        self.outgoing: asyncio.Queue[Message] = asyncio.Queue()
        self.incoming: asyncio.Queue[Message] = asyncio.Queue()
        self.incoming.put_nowait({"type": "websocket.connect"})

        async def send(message: Message) -> None:
            if before_send is not None:
                await before_send(message)
            self.outgoing.put_nowait(message)

        self.socket = WebSocket(
            {
                "type": "websocket",
                "path": "/ws",
                "headers": headers,
                "subprotocols": protocols,
                "app": app,
            },
            self.incoming.get,
            send,
        )
        self.task = asyncio.create_task(realtime.websocket_session(self.socket))

    def input(self, frame: BaseModel) -> None:
        self.input_text(frame.model_dump_json())

    def input_text(self, raw: str) -> None:
        self.incoming.put_nowait({"type": "websocket.receive", "text": raw})

    async def receive(self) -> Message:
        async with asyncio.timeout(1):
            return await self.outgoing.get()

    async def frame(self, expected: str) -> Message:
        message = await self.receive()
        self_type = message["type"]
        if self_type != "websocket.send":
            raise AssertionError(f"Expected a frame, received {message}")
        data: Message = json.loads(message["text"])
        if data["type"] != expected:
            raise AssertionError(f"Expected {expected}, received {data}")
        return data

    async def close(self) -> None:
        if not self.task.done():
            self.incoming.put_nowait({"type": "websocket.disconnect", "code": 1000})
        async with asyncio.timeout(1):
            await self.task


class RealtimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.auth = _Auth()
        self.hub = realtime.Realtime()
        self.app.state.auth_config = AuthConfig(frozenset({_SITE}), local_http=True)
        self.app.state.auth = self.auth
        self.app.state.realtime = self.hub
        self.resource = realtime.Resource(kind="learning_space", id="owned-space")

    def connect(
        self,
        *,
        origin: str = _SITE,
        cookie: str = _COOKIE,
        protocols: list[str] | None = None,
        before_send: Callable[[Message], Awaitable[None]] | None = None,
    ) -> _Peer:
        peer = _Peer(
            self.app,
            [
                (b"host", b"localhost"),
                (b"origin", origin.encode()),
                (b"cookie", cookie.encode()),
            ],
            [realtime.SUBPROTOCOL] if protocols is None else protocols,
            before_send,
        )
        self.addAsyncCleanup(peer.close)
        return peer

    async def ready(self, before_send: Callable[[Message], Awaitable[None]] | None = None) -> _Peer:
        peer = self.connect(before_send=before_send)
        self.assertEqual((await peer.receive())["subprotocol"], "deermind.v1")
        peer.input_text(
            '{"type":"hello","session_id":"'
            + str(self.auth.view.session_id)
            + '","csrf_token":"test-csrf"}'
        )
        await peer.frame("ready")
        return peer

    async def test_upgrade_and_hello_require_bound_origin_cookie_and_protocol(self) -> None:
        for candidate in (
            self.connect(origin="http://127.0.0.1"),
            self.connect(cookie="dm_session_local=incorrect"),
            self.connect(protocols=["another.v1"]),
        ):
            self.assertEqual((await candidate.receive())["type"], "websocket.close")
        peer = self.connect()
        self.assertEqual((await peer.receive())["type"], "websocket.accept")
        peer.input_text('{"type":"hello","session_id":"unrelated","csrf_token":"test-csrf"}')
        self.assertEqual((await peer.receive())["code"], 4401)

    async def test_receipt_error_and_changed_are_separate(self) -> None:
        async def authorize(
            session: SessionView, resource: realtime.Resource, views: frozenset[str]
        ) -> bool:
            return (
                session.account.account_id == self.auth.view.account.account_id
                and resource == self.resource
                and views <= {"conversation"}
            )

        async def handle(session: SessionView, command: realtime.Command) -> realtime.CommandResult:
            self.assertEqual(session.session_id, self.auth.view.session_id)
            if command.request_id == "busy":
                raise RequestError(409, "interaction_busy", "上一条消息处理中。")
            if command.request_id == "uncertain":
                raise RuntimeError("sensitive internal error")
            return realtime.CommandResult(state="accepted", owner_receipt_ref="trace")

        self.hub.authorize = authorize
        peer = await self.ready()
        command = realtime.Command(
            frame_id="command",
            request_id="original",
            action="learning.input",
            resource=self.resource,
            payload={"text": "给我一点提示"},
        )
        peer.input(command)
        self.assertEqual((await peer.frame("error"))["acceptance"], "not_accepted")
        self.hub.commands["learning.input"] = handle
        peer.input(
            command.model_copy(
                update={"resource": self.resource.model_copy(update={"id": "other-space"})}
            )
        )
        self.assertEqual((await peer.frame("error"))["error"]["code"], "not_found")
        peer.input(command.model_copy(update={"request_id": "busy"}))
        busy = await peer.frame("error")
        self.assertEqual(busy["error"]["code"], "interaction_busy")
        self.assertEqual(busy["acceptance"], "not_accepted")
        peer.input(command.model_copy(update={"request_id": "uncertain"}))
        uncertain = await peer.frame("error")
        self.assertEqual(uncertain["acceptance"], "unknown")
        self.assertNotIn("sensitive internal error", str(uncertain))

        peer.input(command)
        receipt = await peer.frame("receipt")
        self.assertEqual(receipt["request_id"], "original")
        self.assertEqual(receipt["owner_receipt_ref"], "trace")

        passive = await self.ready()
        for watcher in (peer, passive):
            watcher.input(
                Watch(
                    frame_id="watch", watch_id="w", resource=self.resource, views=["conversation"]
                )
            )
            await watcher.frame("watch_ready")
        await self.hub.notify("learning_space", "owned-space", ["conversation"], "original")
        self.assertIsNone((await peer.frame("changed"))["request_id"])
        self.assertIsNone((await passive.frame("changed"))["request_id"])
        await self.hub.notify(
            "learning_space",
            "owned-space",
            ["conversation"],
            "original",
            request_account_id=self.auth.view.account.account_id,
        )
        self.assertEqual((await peer.frame("changed"))["request_id"], "original")
        self.assertEqual((await passive.frame("changed"))["request_id"], "original")

    async def test_watch_checks_permission_again_before_sending(self) -> None:
        allowed = True

        async def authorize(
            session: SessionView, resource: realtime.Resource, views: frozenset[str]
        ) -> bool:
            return allowed

        self.hub.authorize = authorize
        peer = await self.ready()
        peer.input(Watch(frame_id="watch", watch_id="w", resource=self.resource, views=["goal"]))
        await peer.frame("watch_ready")
        allowed = False
        await self.hub.notify("learning_space", "owned-space", ["goal"])
        dropped = await peer.frame("resync_required")
        self.assertNotIn("resource", dropped)
        self.assertEqual(dropped["watch_id"], "w")
        self.auth.revoked = True
        peer.input(Heartbeat(type="ping", frame_id="health"))
        self.assertEqual((await peer.receive())["code"], 4401)

    async def test_connections_and_watches_are_bounded(self) -> None:
        async def allow(
            session: SessionView, resource: realtime.Resource, views: frozenset[str]
        ) -> bool:
            return True

        self.hub.authorize = allow
        first = await self.ready()
        for _ in range(3):
            await self.ready()
        denied = self.connect()
        self.assertEqual((await denied.receive())["code"], 1013)
        for index in range(5):
            first.input(
                Watch(
                    frame_id=f"watch-{index}",
                    watch_id=str(index),
                    resource=self.resource,
                    views=["goal"],
                )
            )
            await first.frame("watch_ready" if index < 4 else "error")
        first.input_text('{"type":"unwatch","frame_id":"end","watch_id":"0"}')
        self.assertEqual((await first.frame("unwatch_ready"))["watch_id"], "0")
        first.input(Watch(frame_id="new", watch_id="4", resource=self.resource, views=["events"]))
        await first.frame("watch_ready")

    async def test_global_connection_slot_is_released(self) -> None:
        with patch.object(realtime, "_CONNECTIONS", 1):
            first = await self.ready()
            denied = self.connect()
            self.assertEqual((await denied.receive())["code"], 1013)
            await first.close()
            await self.ready()

    async def test_removed_watch_skips_ack_waiting_for_permission_check(self) -> None:
        started = asyncio.Event()
        released = asyncio.Event()
        checked = False

        async def authorize(
            session: SessionView, resource: realtime.Resource, views: frozenset[str]
        ) -> bool:
            nonlocal checked
            if checked:
                started.set()
                await released.wait()
                return False
            checked = True
            return True

        self.hub.authorize = authorize
        peer = await self.ready()
        peer.input(Watch(frame_id="watch", watch_id="w", resource=self.resource, views=["goal"]))
        async with asyncio.timeout(1):
            await started.wait()
        peer.input_text('{"type":"unwatch","frame_id":"end","watch_id":"w"}')
        # 等到取消订阅被派发，再放行挂起的权限检查。
        async with asyncio.timeout(1):
            while any(connection.watches for connection in self.hub.connections):
                await asyncio.sleep(0)
        released.set()
        self.assertEqual((await peer.frame("unwatch_ready"))["watch_id"], "w")

    async def test_slow_connection_does_not_block_a_healthy_watcher(self) -> None:
        async def allow(
            session: SessionView, resource: realtime.Resource, views: frozenset[str]
        ) -> bool:
            return True

        async def blocked(message: Message) -> None:
            if '"type":"changed"' in message.get("text", ""):
                await asyncio.Event().wait()

        self.hub.authorize = allow
        slow = await self.ready(before_send=blocked)
        fast = await self.ready()
        for peer in (slow, fast):
            peer.input(Watch(frame_id="w", watch_id="w", resource=self.resource, views=["goal"]))
            await peer.frame("watch_ready")
        with patch.object(realtime, "_SEND_SECONDS", 0.05):
            await self.hub.notify("learning_space", "owned-space", ["goal"])
            self.assertEqual((await fast.frame("changed"))["views"], ["goal"])
            self.assertEqual((await slow.receive())["code"], 1013)
        fast.input(Heartbeat(type="ping", frame_id="health"))
        self.assertEqual((await fast.frame("pong"))["frame_id"], "health")

    async def test_outbound_changes_coalesce_and_bound_count_plus_bytes(self) -> None:
        first = realtime._Outbox()  # pyright: ignore[reportPrivateUsage]
        watch = Watch(frame_id="frame", watch_id="watch", resource=self.resource, views=["goal"])
        change = realtime.Changed(watch_id="watch", resource=self.resource, views=["goal"])
        first.put(change.model_copy(update={"request_id": "a"}), watch=watch)
        first.put(change.model_copy(update={"views": ["events"], "request_id": "b"}), watch=watch)
        queued = await first.take()
        self.assertIsInstance(queued.frame, realtime.Changed)
        assert isinstance(queued.frame, realtime.Changed)
        self.assertEqual(queued.frame.views, ["events", "goal"])
        self.assertIsNone(queued.frame.request_id)
        for index in range(33):
            first.put(Heartbeat(type="pong", frame_id=str(index)))
        self.assertEqual(first.failed.result().code, 1013)
        second = realtime._Outbox()  # pyright: ignore[reportPrivateUsage]
        error = Error(
            error=ErrorDetail(code="test", message="字" * 20000, issues=[], retryable=False)
        )
        for _ in range(5):
            second.put(error)
        self.assertEqual(second.failed.result().code, 1013)

    async def test_transport_size_and_strict_encoding(self) -> None:
        peer = await self.ready()
        peer.input_text(
            '{"type":"command","frame_id":"f","request_id":"r","action":"learning.input",'
            '"resource":{"kind":"learning_space","id":"owned-space"},"payload":{"invalid":NaN}}'
        )
        error = await peer.frame("error")
        self.assertEqual(error["request_id"], "r")
        self.assertEqual(error["error"]["code"], "invalid_request")
        with self.assertRaises(ValidationError):
            realtime.INCOMING.validate_json('{"type":"ping","frame_id":"id","unexpected":3}')
        command = realtime.Command(
            frame_id="f",
            request_id="a" * 200,
            action="learning.input",
            resource=self.resource,
            payload={"text": "x" * (realtime.MESSAGE_BYTES - 400)},
        )
        self.assertLess(len(command.model_dump_json().encode()), realtime.MESSAGE_BYTES)
        self.assertGreater(command.business_size(), realtime.MESSAGE_BYTES)
        peer.input(command)
        self.assertEqual((await peer.frame("error"))["error"]["code"], "payload_too_large")
        peer.input_text("字" * (realtime.MESSAGE_BYTES // 3 + 1))
        self.assertEqual((await peer.receive())["code"], 1009)

    async def test_handshake_and_idle_sessions_expire(self) -> None:
        with patch.object(realtime, "_HELLO_SECONDS", 0.05):
            stalled = self.connect()
            self.assertEqual((await stalled.receive())["type"], "websocket.accept")
            self.assertEqual((await stalled.receive())["reason"], "hello timed out")
        with (
            patch.object(realtime, "_HEARTBEAT_SECONDS", 0.01),
            patch.object(realtime, "_IDLE_SECONDS", 60),
        ):
            idle = await self.ready()
            await idle.frame("ping")
            connection = next(iter(self.hub.connections))
            connection.last_heartbeat -= 61
            while (frame := await idle.receive())["type"] == "websocket.send":
                self.assertEqual(json.loads(frame["text"])["type"], "ping")
            self.assertEqual(frame["reason"], "heartbeat timed out")
