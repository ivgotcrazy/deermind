"""只绑定既有持久订阅；创建和调整消息资源由独立维护入口执行。"""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from deermind.foundation.system.delivery.contracts import EventNotice, SubscriptionRegistry
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from nats.aio.client import Client
from nats.js.api import (
    AckPolicy,
    ConsumerConfig,
    DeliverPolicy,
    DiscardPolicy,
    RetentionPolicy,
    StorageType,
    StreamConfig,
)
from nats.js.client import JetStreamContext
from nats.js.errors import NotFoundError

LOGGER = logging.getLogger("runtime")


class MessagingSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    address: str = Field(pattern=r"^nats://[^/@:]+:[0-9]+$")
    deployment: str = Field(pattern=r"^[a-z][a-z0-9-]{0,31}$")
    user: str = Field(min_length=1)
    password: SecretStr

    @classmethod
    def from_environment(cls) -> "MessagingSettings":
        return cls.model_validate(
            {
                field: os.environ[f"M1_NATS_{field.upper()}"]
                for field in cls.model_fields
                if f"M1_NATS_{field.upper()}" in os.environ
            }
        )

    @property
    def stream(self) -> str:
        return "DM_" + self.deployment.upper().replace("-", "_") + "_EVENTS"

    @property
    def failures(self) -> str:
        return "DM_" + self.deployment.upper().replace("-", "_") + "_DELIVERY_FAILURES"

    def subject(self, event_type: str) -> str:
        return f"dm.{self.deployment}.event.{event_type}"


@asynccontextmanager
async def connect(settings: MessagingSettings) -> AsyncGenerator["JetStream"]:
    """重连只恢复连接，不重做业务；关闭不删除消费者或消息。"""

    async def error(error: Exception) -> None:
        LOGGER.warning(
            "消息连接异常，已保存的交接安排仍保留",
            extra={
                "action": "message_connection",
                "outcome": "failed",
                "error_code": type(error).__name__,
            },
        )

    client = Client()
    try:
        async with asyncio.timeout(5):
            await client.connect(
                servers=[settings.address],
                user=settings.user,
                password=settings.password.get_secret_value(),
                connect_timeout=5,
                max_reconnect_attempts=-1,
                reconnect_time_wait=2,
                error_cb=error,
                pending_size=64 * 1024,
            )
        yield JetStream(client, settings)
    finally:
        await client.close()


class JetStream:
    """网络层只处理登记、投递和查询，不能决定谁应当订阅业务事件。"""

    def __init__(self, client: Client, settings: MessagingSettings) -> None:
        self.settings = settings
        self.js = JetStreamContext(client, timeout=5)

    def stream_config(self, *, failure: bool) -> StreamConfig:
        subjects = (
            [
                f"$JS.EVENT.ADVISORY.CONSUMER.{kind}.{self.settings.stream}.*"
                for kind in ("MAX_DELIVERIES", "MSG_TERMINATED")
            ]
            if failure
            else [self.settings.subject("*")]
        )
        return StreamConfig(
            name=self.settings.failures if failure else self.settings.stream,
            subjects=subjects,
            retention=RetentionPolicy.INTEREST,
            storage=StorageType.FILE,
            discard=DiscardPolicy.NEW,
            max_age=0,
            max_msg_size=64 * 1024,
            max_bytes=(32 if failure else 768) * 1024 * 1024,
            num_replicas=1,
            deny_delete=True,
            deny_purge=True,
        )

    def consumer_config(self, name: str, event_types: frozenset[str] | None) -> ConsumerConfig:
        return ConsumerConfig(
            durable_name=name,
            name=name,
            deliver_policy=DeliverPolicy.NEW if event_types else DeliverPolicy.ALL,
            ack_policy=AckPolicy.EXPLICIT,
            ack_wait=30,
            max_deliver=5 if event_types else -1,
            max_ack_pending=1,
            filter_subjects=sorted(self.settings.subject(item) for item in event_types)
            if event_types
            else None,
        )

    async def initialize(self, registry: SubscriptionRegistry) -> None:
        """仅维护凭据使用；已有资源只核对，不覆盖或删除不一致配置。"""
        for failure in (True, False):
            expected = self.stream_config(failure=failure)
            assert expected.name is not None
            try:
                await self.js.stream_info(expected.name)
            except NotFoundError:
                # SDK的**params未标注；仅传入其已声明的StreamConfig。
                await self.js.add_stream(expected)  # pyright: ignore[reportUnknownMemberType]
            await self.check_stream(failure=failure)
            if failure:
                await self._create_consumer(
                    self.settings.failures, self.consumer_config("failure_collector", None)
                )
        for item in registry.items:
            await self._create_consumer(
                self.settings.stream, self.consumer_config(item.subscriber_id, item.event_types)
            )

    async def _create_consumer(self, stream: str, expected: ConsumerConfig) -> None:
        assert expected.durable_name is not None
        try:
            await self.js.consumer_info(stream, expected.durable_name)
        except NotFoundError:
            # 新订阅只收安装后的事件；固定快照使旧事件不会自动加入新订阅。
            # SDK的**params未标注；不使用动态参数扩展。
            await self.js.add_consumer(stream, expected)  # pyright: ignore[reportUnknownMemberType]
        await self._check_consumer(stream, expected)

    async def _check_consumer(self, stream: str, expected: ConsumerConfig) -> None:
        assert expected.durable_name is not None
        actual = (await self.js.consumer_info(stream, expected.durable_name)).config
        for field in ("ack_policy", "ack_wait", "max_deliver", "max_ack_pending"):
            if getattr(actual, field) != getattr(expected, field):
                raise ValueError(f"Consumer configuration mismatch: {field}")
        filters = set(
            actual.filter_subjects or ([actual.filter_subject] if actual.filter_subject else [])
        )
        if filters != set(expected.filter_subjects or []):
            raise ValueError("Consumer filter mismatch")

    async def check_stream(self, *, failure: bool) -> None:
        expected = self.stream_config(failure=failure)
        assert expected.name is not None
        actual = (await self.js.stream_info(expected.name)).config
        for field in (
            "retention",
            "storage",
            "discard",
            "max_age",
            "max_msg_size",
            "max_bytes",
            "deny_delete",
            "deny_purge",
        ):
            if getattr(actual, field) != getattr(expected, field):
                raise ValueError(f"Stream configuration mismatch: {field}")
        if set(actual.subjects or []) != set(expected.subjects or []):
            raise ValueError("Stream subject mismatch")

    async def check_subscribers(
        self, notice: EventNotice, expected: dict[str, str], registry: SubscriptionRegistry
    ) -> None:
        current = {item.subscriber_id: item for item in registry.items}
        for name, revision in expected.items():
            item = current.get(name)
            if (
                item is None
                or item.revision != revision
                or item not in registry.matching(notice.event_type, notice.scope_kind)
            ):
                raise ValueError("Expected subscriber is not registered")
            await self._check_consumer(
                self.settings.stream, self.consumer_config(name, item.event_types)
            )

    async def publish(self, notice: EventNotice) -> tuple[str, int]:
        body = notice.model_dump_json(exclude={"handoff_id"}).encode("utf-8")
        if len(body) > 64 * 1024:
            raise ValueError("Event notice exceeds 64KiB")
        receipt = await self.js.publish(
            self.settings.subject(notice.event_type),
            body,
            headers={"Nats-Msg-Id": str(notice.delivery_id)},
            timeout=5,
        )
        if receipt.stream != self.settings.stream:
            raise ValueError("Publish receipt belongs to a different stream")
        return receipt.stream, receipt.seq
