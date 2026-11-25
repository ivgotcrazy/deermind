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
            # 连接已标记失败，后续帧不再入队。
            return
        replace_at = None
        previous_size = 0
        if isinstance(frame, Changed):
            # 同一订阅的变更帧可合并，避免慢速连接上重复堆积。
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
            # 单帧超过协议上限，标记连接失败。
            self.failed.set_result(_Close(1009, "frame too large"))
            return
        if buffered_size > _OUTGOING_BYTES or (
            replace_at is None and len(self.frames) >= _OUTGOING_FRAMES
        ):
            # 缓冲字节数或帧数超限，判定对端消费过慢并关闭连接。
            self.failed.set_result(_Close(1013, "slow connection"))
            return
        queued = _Queued(frame, raw, size, watch, resource)
        if replace_at is None:
            self.frames.append(queued)
        else:
            # 命中待合并的旧变更帧，原地替换。
            self.frames[replace_at] = queued
        self.size = buffered_size
        self.available.set()

    async def take(self) -> _Queued:
        await self.available.wait()
        result = self.frames.popleft()
        self.size -= result.size
        if not self.frames:
            # 缓冲已清空，关闭就绪事件避免发送侧空转。
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
                    # 资源与已订阅视图有交集才推送。
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
                # 仅通知仍持有订阅的连接做全量重同步。
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
                # 会话已失效、被禁用或冲突，关闭连接。
                raise _Close(4401, "session no longer valid") from error
            raise
        if (
            session.session_id != self.session.session_id
            or session.account.account_id != self.session.account.account_id
            or not _secret_matches(self.session.csrf_token, session.csrf_token)
        ):
            # 重授权后会话或身份发生变化，拒绝沿用旧连接。
            raise _Close(4401, "session no longer valid")
        return session

    async def run(self) -> None:
        try:
            async with asyncio.timeout(_HELLO_SECONDS):
                first = await _text(self.socket)
                hello = INCOMING.validate_json(first)
                if not isinstance(hello, Hello):
                    # 首帧必须是握手消息。
                    raise _Close(1008, "hello required")
                session = await self.current_session()
                if hello.session_id != str(session.session_id) or not _secret_matches(
                    hello.csrf_token.get_secret_value(), session.csrf_token
                ):
                    # 握手携带的会话标识与 CSRF 不一致，拒绝连接。
                    raise _Close(4401, "session confirmation failed")
        except TimeoutError as error:
            # 握手超时，关闭连接。
            raise _Close(1008, "hello timed out") from error
        except ValidationError as error:
            # 握手帧不符合协议合同。
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
                # 缓冲失败事件先于业务任务完成，按其原因关闭连接。
                raise self.outbox.failed.result()
            for task in tasks:
                if task in done:
                    # 已结束的任务抛出异常即向上传播。
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
                # 帧不符合协议合同，回错误后继续读取后续帧。
                self.error("invalid_request", "消息格式无效。")
                continue
            await self.handle(frame)

    async def handle(self, frame: Incoming) -> None:
        if isinstance(frame, Hello):
            # 握手只能出现一次，重复握手视为协议错误。
            raise _Close(1008, "hello already received")
        session = await self.current_session()
        if isinstance(frame, Command):
            # 业务命令交命令处理方。
            await self.command(session, frame)
        elif isinstance(frame, Watch):
            # 订阅资源视图。
            await self.watch(session, frame)
        elif isinstance(frame, Unwatch):
            # 取消订阅并回执，不存在的 watch_id 静默忽略。
            self.watches.pop(frame.watch_id, None)
            self.outbox.put(UnwatchReady(frame_id=frame.frame_id, watch_id=frame.watch_id))
        elif frame.type == "ping":
            # 客户端 ping 直接回 pong 并刷新心跳时间。
            self.last_heartbeat = asyncio.get_running_loop().time()
            self.outbox.put(Heartbeat(type="pong", frame_id=frame.frame_id))
        elif frame.frame_id in self.pings:
            # 服务端 ping 的回声，移出待确认队列并刷新心跳时间。
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
            # 资源类型不符，或正文中夹带请求编号，拒绝命令。
            self.error("invalid_request", "动作的资源或正文不符合要求。", frame)
            return
        try:
            business_size = frame.business_size()
        except ValueError:
            # 正文不是可序列化 JSON。
            self.error("invalid_request", "命令正文必须是有效 JSON。", frame)
            return
        if business_size > MESSAGE_BYTES:
            # 业务载荷超出单帧上限。
            self.error("payload_too_large", "输入超过连接大小限制。", frame)
            return
        handler = self.hub.commands.get(frame.action)
        if handler is None:
            # 未登记该动作的处理方。
            self.error("invalid_request", "此动作当前不可用。", frame)
            return
        if not await self.allowed(session, frame.resource, frozenset()):
            # 无资源访问权限，按不存在处理。
            self.error("not_found", "找不到此资源。", frame)
            return
        try:
            result = await handler(session, frame)
        except RequestConflict:
            # 业务冲突映射为 409 错误帧。
            self.error("request_conflict", "请求身份或内容冲突，请核对后重试。", frame)
            return
        except RequestError as error:
            if error.status < 500:
                # 4xx 业务错误直接回对外错误码，429 标记可重试。
                self.error(error.code, error.message, frame, retryable=error.status == 429)
                return
            # 5xx 视为受理结果未确认。
            self.command_failed(frame, error)
            return
        except Exception as error:
            # 未预期异常同样按结果未确认处理。
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
            # 视图不在资源允许清单内，或存在重复视图。
            self.error("invalid_request", "订阅视图无效。", frame)
            return
        if frame.watch_id not in self.watches and len(self.watches) >= _WATCHES:
            # 新订阅超过单连接订阅数上限。
            self.error("resource_busy", "当前连接的订阅已达上限。", frame)
            return
        if not await self.allowed(session, frame.resource, views):
            # 无资源或视图访问权限。
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
                    # 订阅已被替换或取消，丢弃该旧帧。
                    continue
                frame = queued.frame
                views = frame.views if isinstance(frame, Changed) else watch.views
                session = await self.current_session()
                allowed = await self.allowed(session, watch.resource, frozenset(views))
                if self.watches.get(watch.watch_id) is not watch:
                    # 授权期间订阅状态又发生变化，再次丢弃。
                    continue
                if not allowed:
                    # 授权已收回，移除订阅并要求客户端重同步。
                    del self.watches[watch.watch_id]
                    self.outbox.put(
                        ResyncRequired(watch_id=watch.watch_id, reason="watch_unavailable")
                    )
                    continue
            elif queued.resource is not None:
                session = await self.current_session()
                if not await self.allowed(session, queued.resource, frozenset()):
                    # 非订阅帧对应的资源权限已失效，关闭连接。
                    raise _Close(1008, "resource no longer available")
            try:
                async with asyncio.timeout(_SEND_SECONDS):
                    await self.socket.send_text(queued.text)
            except TimeoutError as error:
                # 发送超时，判定对端消费过慢。
                raise _Close(1013, "slow connection") from error

    async def heartbeat(self) -> None:
        clock = asyncio.get_running_loop().time
        while True:
            await asyncio.sleep(_HEARTBEAT_SECONDS)
            if clock() - self.last_heartbeat >= _IDLE_SECONDS:
                # 超过空闲阈值未收到任何心跳或回声，判定连接挂死。
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
        # 二进制帧不被协议接受。
        raise _Close(1003, "text frames required")
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError as error:
        # 帧内容不是合法 UTF-8。
        raise _Close(1007, "invalid UTF-8") from error
    if size > MESSAGE_BYTES:
        # 帧字节数超出协议上限。
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
        # 来源不可信、缺会话 Cookie 或未协商子协议，拒绝升级。
        await socket.close(code=1008)
        return
    if hub.upgrades >= _CONNECTIONS:
        # 全局连接数已达上限，拒绝新连接。
        await socket.close(code=1013)
        return
    hub.upgrades += 1
    account_id = None
    try:
        async with asyncio.timeout(_HELLO_SECONDS):
            session = await auth.session(token)
        if hub.accounts[session.account.account_id] >= _ACCOUNT_CONNECTIONS:
            # 单账号连接数已达上限，防止同一账号挤占资源。
            raise _Close(1013, "account connection limit")
        account_id = session.account.account_id
        hub.accounts[account_id] += 1
        await socket.accept(subprotocol=SUBPROTOCOL)
        await _Connection(socket, auth, hub, token, session).run()
    except WebSocketDisconnect:
        # 对端主动断开，正常结束。
        pass
    except _Close as error:
        # 协议层主动关闭，携带约定关闭码与原因。
        await _close(socket, error.code, error.reason)
    except AuthError as error:
        # 认证失败：4xx 用 1008，服务端异常用 1011。
        code = 1008 if error.status < 500 else 1011
        await _close(socket, code, "session unavailable")
    except Exception as error:
        # 未预期异常，记录类别后以 1011 关闭，不回显内部细节。
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
                # 该账号已无连接，清空计数避免残留。
                del hub.accounts[account_id]


async def _close(socket: WebSocket, code: int, reason: str) -> None:
    try:
        async with asyncio.timeout(_SEND_SECONDS):
            await socket.close(code=code, reason=reason)
    except (TimeoutError, WebSocketDisconnect, RuntimeError):
        # 对端可能已断开，连接资源仍由外层释放。
        pass
