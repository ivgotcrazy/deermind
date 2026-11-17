"""纯合同校验；不连接数据库或消息服务器。"""

import json
import logging
import unittest
from uuid import uuid4

from deermind.abstractions.delivery import Acceptance, DeliveryNotice, EventNotice
from deermind.foundation.system.delivery.contracts import Subscription, SubscriptionRegistry
from deermind.foundation.system.logging import JsonFormatter
from deermind.infrastructure.nats.connection import MessagingSettings
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection


async def ignore(connection: AsyncConnection, notice: EventNotice) -> Acceptance:
    return Acceptance(disposition="ignored", arrangement_refs=[])


class DeliveryContractTests(unittest.TestCase):
    def test_acceptance_requires_saved_work(self) -> None:
        """不能用空引用声称已经可靠受理。"""
        with self.assertRaises(ValidationError):
            Acceptance(disposition="accepted", arrangement_refs=[])
        with self.assertRaises(ValidationError):
            Acceptance(disposition="rejected", arrangement_refs=[])

    def test_subscription_registry_is_explicit(self) -> None:
        """拒绝重复、通配符和自身递归订阅。"""
        valid = Subscription(
            "receiver", "1", frozenset({"AnswerSubmitted"}), frozenset({"learning_space"}), ignore
        )
        with self.assertRaises(ValueError):
            SubscriptionRegistry([valid, valid])
        for kind in ("*", "DeliveryStateChanged"):
            with self.assertRaises(ValueError):
                SubscriptionRegistry(
                    [Subscription("receiver", "1", frozenset({kind}), valid.scope_kinds, ignore)]
                )

    def test_wire_notice_does_not_include_body_or_internal_handoff(self) -> None:
        """网络格式严格沿合同，正文、额外字段和内部安排号不能混入。"""
        fields = dict(
            delivery_id=uuid4(),
            event_id=uuid4(),
            event_type="AnswerSubmitted",
            schema_version=1,
            producer="interaction",
            scope_kind="learning_space",
            scope_id=uuid4(),
        )
        notice = DeliveryNotice.model_validate(fields)
        for field in ("handoff_id", "payload", "version"):
            with self.assertRaises(ValidationError):
                DeliveryNotice.model_validate({**fields, field: "extra"})
        self.assertEqual(DeliveryNotice.model_validate_json(notice.model_dump_json()), notice)

    def test_credentials_cannot_be_embedded_in_address(self) -> None:
        """连接配置不打印密码，不接受带密码的URL。"""
        with self.assertRaises(ValidationError):
            MessagingSettings(
                address="nats://user:password@host:4222",
                deployment="test",
                user="user",
                password=SecretStr("hidden"),
            )
        settings = MessagingSettings(
            address="nats://host:4222",
            deployment="local-wsl",
            user="application",
            password=SecretStr("hidden"),
        )
        self.assertNotIn("hidden", repr(settings))
        self.assertEqual(settings.stream, "DM_LOCAL_WSL_EVENTS")

    def test_logs_preserve_delivery_identity_without_payload(self) -> None:
        """故障可按事件和订阅定位，不把通知正文复制到日志。"""
        record = logging.LogRecord("runtime", logging.INFO, __file__, 1, "事件已接住", (), None)
        record.event_id = "test-event"
        record.subscriber_id = "test-subscriber"
        record.payload = "private"
        result = json.loads(JsonFormatter().format(record))
        self.assertEqual(result["event_id"], "test-event")
        self.assertEqual(result["subscriber_id"], "test-subscriber")
        self.assertNotIn("private", json.dumps(result))
