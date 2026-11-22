"""Core NATS 中可丢失的页面刷新提示，只传递已提交事件的 ID。"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID

from deermind.infrastructure.nats.connection import MessagingSettings

from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.errors import Error, SlowConsumerError

LOGGER = logging.getLogger("runtime")


class ViewNotices:
    """每个 API 独立订阅。连接故障时客户端仍可从 HTTP 补读。"""

    def __init__(
        self,
        settings: MessagingSettings | None,
        receive: Callable[[UUID], Awaitable[None]],
        resync: Callable[[], Awaitable[None]],
    ) -> None:
        self.settings = settings
        self.receive = receive
        self.resync = resync
        self.ready = asyncio.Event()
        self._client: Client | None = None

    @asynccontextmanager
    async def listen(self) -> AsyncGenerator[None]:
        """启动独立订阅、重试首次连接，并在 API 退出时关闭订阅。"""
        task = asyncio.create_task(self._start(self.settings)) if self.settings else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            if self._client:
                await self._client.close()
            self.ready.clear()

    async def publish(self, event_id: UUID) -> bool:
        """由数据所有者在提交后调用。返回是否已交给本地 NATS 客户端。"""
        client = self._client
        if self.settings is None or client is None or not client.is_connected:
            return False
        subject = f"dm.{self.settings.deployment}.view_changed"
        try:
            await client.publish(subject, str(event_id).encode("ascii"))
        except Error as error:
            await self._error(error)
            return False
        return True

    async def _start(self, settings: MessagingSettings) -> None:
        while True:
            client = Client()
            self._client = client
            try:
                async with asyncio.timeout(5):
                    await client.connect(
                        servers=[settings.address],
                        user=settings.user,
                        password=settings.password.get_secret_value(),
                        connect_timeout=4,
                        max_reconnect_attempts=-1,
                        reconnect_time_wait=2,
                        disconnected_cb=self._disconnected,
                        reconnected_cb=self._reconnected,
                        error_cb=self._error,
                        pending_size=64 * 1024,
                    )
                    # SDK的可选future参数缺少泛型；回调模式不传future。
                    await client.subscribe(  # pyright: ignore[reportUnknownMemberType]
                        f"dm.{settings.deployment}.view_changed",
                        cb=self._message,
                        pending_msgs_limit=128,
                        pending_bytes_limit=32 * 1024,
                    )
                    await client.flush(timeout=3)
            except (Error, OSError, TimeoutError) as error:
                await self._error(error)
                await client.close()
                await asyncio.sleep(2)
            else:
                await self._reconnected()
                return

    async def _disconnected(self) -> None:
        self.ready.clear()

    async def _reconnected(self) -> None:
        self.ready.set()
        await self.resync()

    async def _error(self, error: Exception) -> None:
        LOGGER.warning(
            "页面刷新提示暂不可用",
            extra={
                "action": "view_notice",
                "outcome": "failed",
                "error_code": type(error).__name__,
            },
        )
        if isinstance(error, SlowConsumerError):
            await self.resync()

    async def _message(self, message: Msg) -> None:
        if len(message.data) != 36:
            return
        try:
            event_id = UUID(message.data.decode("ascii"))
        except ValueError:
            return
        await self.receive(event_id)
