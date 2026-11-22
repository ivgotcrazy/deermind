"""同源 WebSocket、授权订阅和有限的连接缓冲。"""

import asyncio
import logging
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import compare_digest
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from deermind.entrypoints.api.realtime_protocol import (
    ACTION_RESOURCES,
    INCOMING,
    MESSAGE_BYTES,
    RESOURCE_VIEWS,
    SUBPROTOCOL,
    Changed,
    Command,
    CommandResult,
    Error,
    Frame,
    Heartbeat,
    Hello,
    Incoming,
    Ready,
    Receipt,
    Resource,
    ResyncRequired,
    Unwatch,
    UnwatchReady,
    Watch,
    WatchReady,
)
from deermind.foundation.system.public.errors import ErrorDetail, RequestError
from deermind.product.public.auth_config import AuthConfig
from deermind.product.public.authentication import Authentication, AuthError, SessionView
from deermind.product.public.errors import RequestConflict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

__all__ = ["Command", "CommandResult", "Realtime", "Resource", "router"]

router = APIRouter()
LOGGER = logging.getLogger("runtime.websocket")

_CONNECTIONS = 64
_ACCOUNT_CONNECTIONS = 4
_WATCHES = 4
_OUTGOING_FRAMES = 32
_OUTGOING_BYTES = 256 * 1024
_SEND_SECONDS = 10
_HELLO_SECONDS = 10
_HEARTBEAT_SECONDS = 30
_IDLE_SECONDS = 90

type CommandHandler = Callable[[SessionView, Command], Awaitable[CommandResult]]
type Authorize = Callable[[SessionView, Resource, frozenset[str]], Awaitable[bool]]


class _Close(Exception):
    def __init__(self, code: int, reason: str) -> None:
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class _Queued:
    frame: Frame
    text: str
    size: int
    watch: Watch | None
    resource: Resource | None


class _Outbox:
    def __init__(self) -> None:
        self.frames: deque[_Queued] = deque()
        self.size = 0
        self.available = asyncio.Event()
        self.failed: asyncio.Future[_Close] = asyncio.get_running_loop().create_future()

    def put(
        self, frame: Frame, *, watch: Watch | None = None, resource: Resource | None = None
    ) -> None:
        if self.failed.done():
            return
        replace_at = None
        previous_size = 0
        if isinstance(frame, Changed):
            for index, queued in enumerate(self.frames):
                if queued.watch is watch and isinstance(queued.frame, Changed):
                    previous = queued.frame
                    request_id = (
                        frame.request_id if frame.request_id == previous.request_id else None
                    )
                    frame = frame.model_copy(
                        update={
                            "views": sorted(set(frame.views) | set(previous.views)),
                            "request_id": request_id,
                        }
                    )
                    replace_at = index
                    previous_size = queued.size
                    break
        raw = frame.model_dump_json()
        size = len(raw.encode("utf-8"))
        buffered_size = self.size - previous_size + size
        if size > MESSAGE_BYTES:
            self.failed.set_result(_Close(1009, "frame too large"))
            return
        if buffered_size > _OUTGOING_BYTES or (
            replace_at is None and len(self.frames) >= _OUTGOING_FRAMES
        ):
            self.failed.set_result(_Close(1013, "slow connection"))
            return
        queued = _Queued(frame, raw, size, watch, resource)
        if replace_at is None:
            self.frames.append(queued)
        else:
            self.frames[replace_at] = queued
        self.size = buffered_size
        self.available.set()

    async def take(self) -> _Queued:
        await self.available.wait()
        result = self.frames.popleft()
        self.size -= result.size
        if not self.frames:
            self.available.clear()
        return result


class Realtime:
    """连接只保存订阅和刷新提示。业务工作由已登记的处理方保存。"""

    def __init__(
        self,
        *,
        commands: Mapping[str, CommandHandler] | None = None,
        authorize: Authorize | None = None,
        views: Mapping[str, frozenset[str]] | None = None,
    ) -> None:
        self.commands = dict(commands or {})
        self.authorize = authorize
        self.views = RESOURCE_VIEWS | dict(views or {})
        self.connections: set[_Connection] = set()
        self.upgrades = 0
        self.accounts: Counter[UUID] = Counter()

    async def notify(
        self,
        resource_kind: str,
        resource_id: str,
        views: Iterable[str],
        request_id: str | None = None,
        *,
        request_account_id: UUID | None = None,
    ) -> None:
        resource = Resource(kind=resource_kind, id=resource_id)
        requested_views = set(views)
        for connection in self.connections:
            for watch in connection.watches.values():
                relevant = requested_views.intersection(watch.views)
                if resource == watch.resource and relevant:
                    # 未核实请求归属时只发送刷新范围。
                    own_request = request_account_id == connection.session.account.account_id
                    connection.outbox.put(
                        Changed(
                            watch_id=watch.watch_id,
                            resource=resource,
                            views=sorted(relevant),
                            request_id=request_id if own_request else None,
                        ),
                        watch=watch,
                    )

    async def resync(self) -> None:
        for connection in self.connections:
            if connection.watches:
                connection.outbox.put(
                    ResyncRequired(watch_id=None, reason="notification_connection_restored")
                )


class _Connection:
    def __init__(
        self,
        socket: WebSocket,
        service: Authentication,
        hub: Realtime,
        token: str,
        session: SessionView,
    ) -> None:
        self.socket = socket
        self.service = service
        self.hub = hub
        self.token = token
        self.session = session
        self.id = str(uuid4())
        self.watches: dict[str, Watch] = {}
        self.outbox = _Outbox()
        self.pings: deque[str] = deque(maxlen=3)
        self.last_heartbeat = asyncio.get_running_loop().time()

    async def current_session(self) -> SessionView:
        try:
            session = await self.service.session(self.token, str(self.session.session_id))
        except AuthError as error:
            if error.status in {401, 403, 404, 409}:
                raise _Close(4401, "session no longer valid") from error
            raise
        if (
            session.session_id != self.session.session_id
            or session.account.account_id != self.session.account.account_id
            or not _secret_matches(self.session.csrf_token, session.csrf_token)
        ):
            raise _Close(4401, "session no longer valid")
        return session

    async def run(self) -> None:
        try:
            async with asyncio.timeout(_HELLO_SECONDS):
                first = await _text(self.socket)
                hello = INCOMING.validate_json(first)
                if not isinstance(hello, Hello):
                    raise _Close(1008, "hello required")
                session = await self.current_session()
                if hello.session_id != str(session.session_id) or not _secret_matches(
                    hello.csrf_token.get_secret_value(), session.csrf_token
                ):
                    raise _Close(4401, "session confirmation failed")
        except TimeoutError as error:
            raise _Close(1008, "hello timed out") from error
        except ValidationError as error:
            raise _Close(1008, "invalid hello") from error

        self.last_heartbeat = asyncio.get_running_loop().time()
        server_time = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        self.outbox.put(Ready(connection_id=self.id, server_time=server_time))
        self.hub.connections.add(self)
        tasks = [
            asyncio.create_task(self.dispatch()),
            asyncio.create_task(self.send()),
            asyncio.create_task(self.heartbeat()),
        ]
        try:
            done, _ = await asyncio.wait(
                [*tasks, self.outbox.failed], return_when=asyncio.FIRST_COMPLETED
            )
            if self.outbox.failed in done:
                raise self.outbox.failed.result()
            for task in tasks:
                if task in done:
                    task.result()
        finally:
            self.hub.connections.discard(self)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def dispatch(self) -> None:
        while True:
            # Uvicorn 已限制接收队列，按顺序读取，避免额外堆积请求。
            raw = await _text(self.socket)
            try:
                frame = INCOMING.validate_json(raw)
            except ValidationError:
                self.error("invalid_request", "消息格式无效。")
                continue
            await self.handle(frame)

    async def handle(self, frame: Incoming) -> None:
        if isinstance(frame, Hello):
            raise _Close(1008, "hello already received")
        session = await self.current_session()
        if isinstance(frame, Command):
            await self.command(session, frame)
        elif isinstance(frame, Watch):
            await self.watch(session, frame)
        elif isinstance(frame, Unwatch):
            self.watches.pop(frame.watch_id, None)
            self.outbox.put(UnwatchReady(frame_id=frame.frame_id, watch_id=frame.watch_id))
        elif frame.type == "ping":
            self.last_heartbeat = asyncio.get_running_loop().time()
            self.outbox.put(Heartbeat(type="pong", frame_id=frame.frame_id))
        elif frame.frame_id in self.pings:
            self.pings.remove(frame.frame_id)
            self.last_heartbeat = asyncio.get_running_loop().time()

    async def allowed(
        self, session: SessionView, resource: Resource, views: frozenset[str]
    ) -> bool:
        authorize = self.hub.authorize
        return authorize is not None and await authorize(session, resource, views)

    async def command(self, session: SessionView, frame: Command) -> None:
        expected = ACTION_RESOURCES.get(frame.action)
        if (
            expected is not None and expected != frame.resource.kind
        ) or "request_id" in frame.payload:
            self.error("invalid_request", "动作的资源或正文不符合要求。", frame)
            return
        try:
            business_size = frame.business_size()
        except ValueError:
            self.error("invalid_request", "命令正文必须是有效 JSON。", frame)
            return
        if business_size > MESSAGE_BYTES:
            self.error("payload_too_large", "输入超过连接大小限制。", frame)
            return
        handler = self.hub.commands.get(frame.action)
        if handler is None:
            self.error("invalid_request", "此动作当前不可用。", frame)
            return
        if not await self.allowed(session, frame.resource, frozenset()):
            self.error("not_found", "找不到此资源。", frame)
            return
        try:
            result = await handler(session, frame)
        except RequestConflict:
            self.error("request_conflict", "请求身份或内容冲突，请核对后重试。", frame)
            return
        except RequestError as error:
            if error.status < 500:
                self.error(error.code, error.message, frame, retryable=error.status == 429)
                return
            self.command_failed(frame, error)
            return
        except Exception as error:
            self.command_failed(frame, error)
            return
        self.outbox.put(
            Receipt(
                frame_id=frame.frame_id,
                request_id=frame.request_id,
                state=result.state,
                owner_receipt_ref=result.owner_receipt_ref,
                execution_ref=result.execution_ref,
                result_refs=result.result_refs,
            ),
            resource=frame.resource,
        )

    def command_failed(self, frame: Command, error: Exception) -> None:
        # 业务接口异常可能发生在保存后。客户端用原请求编号查询权威收据。
        LOGGER.warning(
            "未确认 WebSocket 命令受理结果",
            extra={
                "action": "websocket_command",
                "outcome": "failed",
                "error_code": type(error).__name__,
            },
        )
        self.error(
            "temporarily_unavailable",
            "暂未确认受理，请查询原请求。",
            frame,
            unknown=True,
            retryable=True,
        )

    async def watch(self, session: SessionView, frame: Watch) -> None:
        views = frozenset(frame.views)
        if not views <= self.hub.views.get(frame.resource.kind, frozenset()) or len(views) != len(
            frame.views
        ):
            self.error("invalid_request", "订阅视图无效。", frame)
            return
        if frame.watch_id not in self.watches and len(self.watches) >= _WATCHES:
            self.error("resource_busy", "当前连接的订阅已达上限。", frame)
            return
        if not await self.allowed(session, frame.resource, views):
            self.error("not_found", "找不到此资源。", frame)
            return
        self.watches[frame.watch_id] = frame
        self.outbox.put(
            WatchReady(
                frame_id=frame.frame_id,
                watch_id=frame.watch_id,
                resource=frame.resource,
                views=frame.views,
            ),
            watch=frame,
        )

    async def send(self) -> None:
        while True:
            queued = await self.outbox.take()
            watch = queued.watch
            if watch is not None:
                if self.watches.get(watch.watch_id) is not watch:
                    continue
                frame = queued.frame
                views = frame.views if isinstance(frame, Changed) else watch.views
                session = await self.current_session()
                allowed = await self.allowed(session, watch.resource, frozenset(views))
                if self.watches.get(watch.watch_id) is not watch:
                    continue
                if not allowed:
                    del self.watches[watch.watch_id]
                    self.outbox.put(
                        ResyncRequired(watch_id=watch.watch_id, reason="watch_unavailable")
                    )
                    continue
            elif queued.resource is not None:
                session = await self.current_session()
                if not await self.allowed(session, queued.resource, frozenset()):
                    raise _Close(1008, "resource no longer available")
            try:
                async with asyncio.timeout(_SEND_SECONDS):
                    await self.socket.send_text(queued.text)
            except TimeoutError as error:
                raise _Close(1013, "slow connection") from error

    async def heartbeat(self) -> None:
        clock = asyncio.get_running_loop().time
        while True:
            await asyncio.sleep(_HEARTBEAT_SECONDS)
            if clock() - self.last_heartbeat >= _IDLE_SECONDS:
                raise _Close(1008, "heartbeat timed out")
            await self.current_session()
            frame_id = str(uuid4())
            self.pings.append(frame_id)
            self.outbox.put(Heartbeat(type="ping", frame_id=frame_id))

    def error(
        self,
        code: str,
        message: str,
        frame: Command | Watch | None = None,
        *,
        unknown: bool = False,
        retryable: bool = False,
    ) -> None:
        self.outbox.put(
            Error(
                frame_id=frame.frame_id if frame is not None else None,
                request_id=frame.request_id if isinstance(frame, Command) else None,
                error=ErrorDetail(code=code, message=message, issues=[], retryable=retryable),
                acceptance="unknown" if unknown else "not_accepted",
            )
        )


def _secret_matches(given: str, expected: str) -> bool:
    return compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


async def _text(socket: WebSocket) -> str:
    message = await socket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect()
    raw = message.get("text")
    if not isinstance(raw, str):
        raise _Close(1003, "text frames required")
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError as error:
        raise _Close(1007, "invalid UTF-8") from error
    if size > MESSAGE_BYTES:
        raise _Close(1009, "frame too large")
    return raw


def _same_origin(socket: WebSocket, config: AuthConfig) -> bool:
    origins = socket.headers.getlist("origin")
    return (
        len(origins) == 1
        and origins[0] in config.origins
        and socket.headers.getlist("host") == [urlsplit(origins[0]).netloc]
        and socket.headers.get("sec-fetch-site") != "cross-site"
    )


@router.websocket("/ws")
async def websocket_session(socket: WebSocket) -> None:
    hub: Realtime = socket.app.state.realtime
    auth: Authentication = socket.app.state.auth
    config: AuthConfig = socket.app.state.auth_config
    token = socket.cookies.get(config.cookie_name)
    if (
        not _same_origin(socket, config)
        or not token
        or SUBPROTOCOL not in socket.scope.get("subprotocols", [])
    ):
        await socket.close(code=1008)
        return
    if hub.upgrades >= _CONNECTIONS:
        await socket.close(code=1013)
        return
    hub.upgrades += 1
    account_id = None
    try:
        async with asyncio.timeout(_HELLO_SECONDS):
            session = await auth.session(token)
        if hub.accounts[session.account.account_id] >= _ACCOUNT_CONNECTIONS:
            raise _Close(1013, "account connection limit")
        account_id = session.account.account_id
        hub.accounts[account_id] += 1
        await socket.accept(subprotocol=SUBPROTOCOL)
        await _Connection(socket, auth, hub, token, session).run()
    except WebSocketDisconnect:
        pass
    except _Close as error:
        await _close(socket, error.code, error.reason)
    except AuthError as error:
        code = 1008 if error.status < 500 else 1011
        await _close(socket, code, "session unavailable")
    except Exception as error:
        LOGGER.warning(
            "WebSocket 连接处理失败",
            extra={
                "action": "websocket_connection",
                "outcome": "failed",
                "error_code": type(error).__name__,
            },
        )
        await _close(socket, 1011, "connection unavailable")
    finally:
        hub.upgrades -= 1
        if account_id is not None:
            hub.accounts[account_id] -= 1
            if not hub.accounts[account_id]:
                del hub.accounts[account_id]


async def _close(socket: WebSocket, code: int, reason: str) -> None:
    try:
        async with asyncio.timeout(_SEND_SECONDS):
            await socket.close(code=code, reason=reason)
    except (TimeoutError, WebSocketDisconnect, RuntimeError):
        # 对端可能已断开，连接资源仍由外层释放。
        pass
