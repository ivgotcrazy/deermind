"""真实PG中的原子保存测试；每例使用独立随机库，不写现有业务数据。"""

import asyncio
import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID, uuid4

from deermind.abstractions.events import EventConflict, EventDraft, ProducerAccess, Ref, StoredEvent
from deermind.bootstrap.events import event_store
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.events.store import EventStore
from deermind.infrastructure.database.connection import application_engine
from deermind.product.accounts.facts import AccountFact
from deermind.product.accounts.projections import apply_account_events
from deermind.product.accounts.save import save_initial_account
from deermind.product.persistence.receipts import Receipt, RequestConflict
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection
from test_database import DatabaseTestCase


class AtomicFactsTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        self.account_id = uuid4()
        self.actor = Ref(owner="runtime", type="service", id="bootstrap")
        self.access = ProducerAccess(
            "product", self.actor, frozenset({("account", self.account_id)})
        )

    async def save(
        self, store: EventStore | None = None, *, display_name: str = "管理员"
    ) -> Receipt:
        engine = application_engine(self.app)
        try:
            return await save_initial_account(
                engine,
                store or event_store(),
                self.access,
                request_id="fixed-request",
                account_id=self.account_id,
                login_identifier="admin",
                display_name=display_name,
            )
        finally:
            await engine.dispose()

    def counts(self) -> list[int]:
        with self.engine.connect() as connection:
            return [
                connection.scalar(text(f"SELECT count(*) FROM {table}"))
                for table in (
                    "runtime.events",
                    "runtime.scope_event_heads",
                    "runtime.projection_receipts",
                    "product.accounts",
                    "product.command_receipt",
                )
            ]

    def draft(self, account_id: UUID | None = None, *, login: str | None = None) -> EventDraft:
        identity = account_id or self.account_id
        fact = AccountFact(
            account_id=identity,
            login_identifier=login or str(identity),
            display_name="测试",
            role="admin",
            status="active",
            revision=1,
            created_at=datetime.now(UTC),
        )
        return EventDraft(
            event_id=uuid4(),
            event_type="TrialAccountSaved",
            schema_version=1,
            scope_kind="account",
            scope_id=identity,
            owner_ref=Ref(owner="product", type="account", id=str(identity), revision=1),
            source_request_id="batch-request",
            payload={
                "account_id": str(identity),
                "action": "bootstrap_admin",
                "account_revision": 1,
                "relation_refs": [],
                "records": [
                    {
                        "record_id": "account",
                        "record_type": "product.accounts",
                        "schema_version": 1,
                        "content": {"storage": "inline", "value": fact.model_dump(mode="json")},
                    }
                ],
            },
        )

    async def append(self, drafts: list[EventDraft], access: ProducerAccess | None = None) -> None:
        engine = application_engine(self.app)
        try:
            async with engine.begin() as connection:
                events = await event_store().append(
                    connection,
                    access or self.access,
                    drafts,
                    commit_id=uuid4(),
                    correlation_id=uuid4(),
                    expected_seq={(d.scope_kind, d.scope_id): 0 for d in drafts},
                )
                await apply_account_events(connection, events)
        finally:
            await engine.dispose()

    def test_commit_and_duplicate(self) -> None:
        """重复请求返回同一收据；完整正文与投影逐字段一致。"""
        first = asyncio.run(self.save())
        self.assertEqual(asyncio.run(self.save()), first)
        self.assertEqual(self.counts(), [1, 1, 1, 1, 1])
        with self.engine.connect() as connection:
            event = connection.execute(text("SELECT * FROM runtime.events")).mappings().one()
            account = connection.execute(text("SELECT * FROM product.accounts")).mappings().one()
            content = event["payload"]["records"][0]["content"]["value"]
            fact = AccountFact.model_validate_json(json.dumps(content))
            self.assertEqual(
                dict(account), {**fact.model_dump(), "source_event_id": event["event_id"]}
            )
            self.assertEqual(event["scope_event_seq"], 1)
            self.assertEqual(event["recorded_at"], event["occurred_at"])
            receipt = (
                connection.execute(text("SELECT * FROM product.command_receipt")).mappings().one()
            )
            self.assertEqual(receipt["state"], "completed")
            self.assertEqual(receipt["request_ref"], event["correlation_id"])

    def test_same_key_different_input(self) -> None:
        asyncio.run(self.save())
        with self.assertRaises(RequestConflict):
            asyncio.run(self.save(display_name="其他名称"))
        self.assertEqual(self.counts(), [1, 1, 1, 1, 1])

    def test_concurrent_duplicate(self) -> None:
        async def race() -> list[Receipt]:
            return list(await asyncio.gather(self.save(), self.save()))

        results = asyncio.run(race())
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.counts(), [1, 1, 1, 1, 1])

    def test_projection_failure_rolls_back_and_retry(self) -> None:
        """先实际插入账号再抛错，五张表均不得留下记录或序号缺口。"""

        async def broken(connection: AsyncConnection, events: list[StoredEvent]) -> None:
            await apply_account_events(connection, events)
            raise RuntimeError("Injected projection failure")

        with patch("deermind.product.accounts.save.apply_account_events", side_effect=broken):
            with self.assertRaisesRegex(RuntimeError, "Injected"):
                asyncio.run(self.save())
        self.assertEqual(self.counts(), [0, 0, 0, 0, 0])
        asyncio.run(self.save())
        self.assertEqual(self.counts(), [1, 1, 1, 1, 1])

    def test_receipt_failure_rolls_back(self) -> None:
        with patch(
            "deermind.product.accounts.save.complete_request",
            side_effect=RuntimeError("receipt failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "receipt failed"):
                asyncio.run(self.save())
        self.assertEqual(self.counts(), [0, 0, 0, 0, 0])

    def test_missing_or_mismatched_records(self) -> None:
        draft = self.draft()
        variants = [
            {**draft.payload, "records": []},
            {**draft.payload, "account_id": str(uuid4())},
            {**draft.payload, "unexpected": "not allowed"},
        ]
        for payload in variants:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                asyncio.run(self.append([replace(draft, payload=payload)]))
            self.assertEqual(self.counts(), [0, 0, 0, 0, 0])

    def test_scope_and_registration_rejection(self) -> None:
        draft = self.draft()
        with self.assertRaises(PermissionError):
            asyncio.run(self.append([draft], replace(self.access, producer="interaction")))
        for invalid in (
            replace(draft, event_type="Unregistered"),
            replace(draft, schema_version=2),
            replace(draft, source_request_id=None),
            replace(draft, causation_event_id=draft.event_id),
        ):
            with self.assertRaises(ValueError):
                asyncio.run(self.append([invalid]))
        self.assertEqual(self.counts(), [0, 0, 0, 0, 0])

    def test_database_constraint_failure_rolls_back(self) -> None:
        """不同账号使用相同登录名，SQL唯一约束失败不能留下第二份事件/收据。"""
        asyncio.run(self.save())
        self.account_id = uuid4()
        self.access = replace(self.access, scopes=frozenset({("account", self.account_id)}))
        with self.assertRaises(DBAPIError):
            asyncio.run(self.save())
        self.assertEqual(self.counts(), [1, 1, 1, 1, 1])

    def test_stale_sequence(self) -> None:
        asyncio.run(self.append([self.draft()]))
        with self.assertRaises(EventConflict):
            asyncio.run(self.append([self.draft()]))
        self.assertEqual(self.counts(), [1, 1, 1, 1, 0])

    def test_batch_and_causation(self) -> None:
        first, second = self.draft(), self.draft(uuid4())
        second = replace(second, causation_event_id=first.event_id, source_request_id=None)
        access = replace(
            self.access, scopes=frozenset({("account", d.scope_id) for d in (first, second)})
        )
        asyncio.run(self.append([first, second], access))
        self.assertEqual(self.counts(), [2, 2, 2, 2, 0])
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT count(DISTINCT commit_id) FROM runtime.events")), 1
            )
            self.assertEqual(
                connection.scalar(
                    text("SELECT causation_event_id FROM runtime.events WHERE event_id=:id"),
                    {"id": second.event_id},
                ),
                first.event_id,
            )

    def test_later_batch_failure_rolls_back_first_event(self) -> None:
        """第二件事件投影撞唯一键时，第一件事件和两个范围序号也一起回滚。"""
        first = self.draft()
        second = self.draft(uuid4(), login=str(self.account_id))
        access = replace(
            self.access, scopes=frozenset({("account", d.scope_id) for d in (first, second)})
        )
        with self.assertRaises(DBAPIError):
            asyncio.run(self.append([first, second], access))
        self.assertEqual(self.counts(), [0, 0, 0, 0, 0])

    def test_existing_cause_requires_authorized_source(self) -> None:
        """知道源事件ID不能代替读取授权；获准后仍由FK检查真实存在。"""
        first = self.draft()
        asyncio.run(self.append([first]))
        second = replace(self.draft(uuid4()), causation_event_id=first.event_id)
        access = replace(self.access, scopes=frozenset({("account", second.scope_id)}))
        with self.assertRaises(PermissionError):
            asyncio.run(self.append([second], access))
        self.assertEqual(self.counts(), [1, 1, 1, 1, 0])
        asyncio.run(
            self.append([second], replace(access, source_event_ids=frozenset({first.event_id})))
        )
        self.assertEqual(self.counts(), [2, 2, 2, 2, 0])

    def test_append_only_permissions(self) -> None:
        asyncio.run(self.save())

        async def forbidden(statement: str) -> None:
            engine = application_engine(self.app)
            try:
                async with engine.begin() as connection:
                    await connection.execute(text(statement))
            finally:
                await engine.dispose()

        for table in ("runtime.events", "runtime.projection_receipts"):
            for statement in (
                f"DELETE FROM {table}",
                f"UPDATE {table} SET event_id=event_id",
                f"TRUNCATE {table}",
            ):
                with (
                    self.subTest(statement=statement),
                    self.assertRaisesRegex(DBAPIError, "permission denied"),
                ):
                    asyncio.run(forbidden(statement))
        self.assertEqual(self.counts(), [1, 1, 1, 1, 1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
