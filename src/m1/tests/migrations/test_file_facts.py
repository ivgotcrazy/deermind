"""真实PG中验证附件、事件和投影；故障数据只写随机测试库和临时目录。"""

import asyncio
import io
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.bootstrap.events import event_store
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from deermind.product.accounts.projections import apply_account_events
from deermind.product.persistence.receipts import claim_request, complete_request
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_database import DatabaseTestCase


class FileFactsTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.files = LocalFiles(Path(self.directory.name), backend="local")
        self.identity = uuid4()
        self.access = ProducerAccess(
            "product",
            Ref(owner="runtime", type="service", id="test"),
            frozenset({("account", self.identity)}),
        )

    def draft(self, size: int) -> EventDraft:
        """固定合法账号DTO，补长展示名以精确覆盖UTF-8字节边界。"""
        value: dict[str, JsonValue] = {
            "account_id": str(self.identity),
            "login_identifier": "test",
            "display_name": "中",
            "role": "admin",
            "status": "active",
            "revision": 1,
            "created_at": "2026-11-16T00:00:00Z",
        }
        value["display_name"] = "中" + "x" * (size - len(canonical_json(value).encode()))
        return EventDraft(
            event_id=uuid4(),
            event_type="TrialAccountSaved",
            schema_version=1,
            scope_kind="account",
            scope_id=self.identity,
            owner_ref=Ref(owner="product", type="account", id=str(self.identity), revision=1),
            payload={
                "account_id": str(self.identity),
                "action": "bootstrap_admin",
                "account_revision": 1,
                "relation_refs": [],
                "records": [
                    {
                        "record_id": "account",
                        "record_type": "product.accounts",
                        "schema_version": 1,
                        "content": {"storage": "inline", "value": value},
                    }
                ],
            },
            source_request_id="file-test",
        )

    async def save(self, draft: EventDraft, *, fail: bool = False) -> None:
        engine = application_engine(self.app)
        try:
            store = event_store()
            prepared = await FactAttachments(engine, self.files).prepare(
                store, self.access, (draft,)
            )
            async with engine.begin() as connection:
                receipt = await claim_request(
                    connection,
                    principal_id="test",
                    action="bootstrap_admin",
                    scope_id=str(self.identity),
                    request_id="file-test",
                    normalized_input=draft.payload,
                )
                if receipt.result_ref is not None:
                    return
                events = await store.append(
                    connection,
                    self.access,
                    prepared,
                    commit_id=uuid4(),
                    correlation_id=uuid4(),
                    expected_seq={("account", self.identity): 0},
                )
                await apply_account_events(connection, events)
                if fail:
                    raise RuntimeError("Fail after producer projection")
                await complete_request(connection, receipt, draft.owner_ref)
        finally:
            await engine.dispose()

    def test_inline_boundary(self) -> None:
        asyncio.run(self.save(self.draft(32 * 1024)))
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM runtime.file_objects")), 0
            )
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM runtime.events")), 1)

    def test_external_round_trip_and_duplicate(self) -> None:
        draft = self.draft(32 * 1024 + 1)
        asyncio.run(self.save(draft))
        asyncio.run(self.save(draft))
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM runtime.file_objects")), 1
            )
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM runtime.events")), 2)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM product.accounts")), 1)
            payload = connection.scalar(
                text("SELECT payload FROM runtime.events WHERE event_type='TrialAccountSaved'")
            )
            reference = payload["records"][0]["content"]
            self.assertEqual(set(reference), {"storage", "file_id", "sha256", "media_type"})
            self.assertEqual(reference["storage"], "file")
            file = connection.execute(text("SELECT * FROM runtime.file_objects")).mappings().one()
            content = json.loads((self.files.root / file["storage_key"]).read_bytes())
            self.assertEqual(
                connection.scalar(text("SELECT display_name FROM product.accounts")),
                content["display_name"],
            )
            self.assertEqual(
                connection.scalar(text("SELECT state FROM product.command_receipt")), "completed"
            )

    def test_failed_business_keeps_only_prepared_file(self) -> None:
        draft = self.draft(33000)
        with self.assertRaisesRegex(RuntimeError, "Fail after"):
            asyncio.run(self.save(draft, fail=True))
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM runtime.events")), 1)
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM product.accounts")), 0)
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM product.command_receipt")), 0
            )
        asyncio.run(self.save(draft))
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM runtime.file_objects")), 1
            )

    def test_file_failure_does_not_submit_facts(self) -> None:
        with patch.object(self.files, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                asyncio.run(self.save(self.draft(33000)))
        with self.engine.connect() as connection:
            for table in (
                "runtime.events",
                "runtime.file_objects",
                "product.accounts",
                "product.command_receipt",
            ):
                self.assertEqual(connection.scalar(text(f"SELECT count(*) FROM {table}")), 0)

    def test_failed_readback_does_not_register_file(self) -> None:
        with patch.object(self.files, "read", side_effect=OSError("corrupt after write")):
            with self.assertRaises(OSError):
                asyncio.run(self.save(self.draft(33000)))
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM runtime.events")), 0)
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM runtime.file_objects")), 0
            )

    def test_corruption_and_missing_before_retry(self) -> None:
        draft = self.draft(33000)
        with self.assertRaises(RuntimeError):
            asyncio.run(self.save(draft, fail=True))
        path = next(self.files.root.glob("*.blob"))
        path.chmod(0o600)
        content = path.read_bytes()
        path.write_bytes(b"!" + content[1:])
        with self.assertRaises(OSError):
            asyncio.run(self.save(draft))
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            asyncio.run(self.save(draft))
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM product.accounts")), 0)

    def test_same_identity_different_content_is_rejected(self) -> None:
        draft = self.draft(33000)
        with self.assertRaises(RuntimeError):
            asyncio.run(self.save(draft, fail=True))
        changed = replace(self.draft(33001), event_id=draft.event_id)
        with self.assertRaisesRegex(ValueError, "identity conflicts"):
            asyncio.run(self.save(changed))

    def test_large_envelope_is_atomic_failure(self) -> None:
        draft = replace(self.draft(33000), source_request_id="x" * (1024 * 1024))
        with self.assertRaisesRegex(ValueError, "exceeds 1MiB"):
            asyncio.run(self.save(draft))
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM product.accounts")), 0)
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM product.command_receipt")), 0
            )
            self.assertEqual(
                connection.scalar(
                    text("SELECT count(*) FROM runtime.events WHERE event_type='TrialAccountSaved'")
                ),
                0,
            )

    def test_envelope_below_limit(self) -> None:
        draft = replace(self.draft(300), source_request_id="x" * (1024 * 1024 - 4096))
        asyncio.run(self.save(draft))
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM product.accounts")), 1)

    def test_prepared_metadata_cannot_be_changed(self) -> None:
        async def check() -> None:
            engine = application_engine(self.app)
            try:
                store = event_store()
                draft = self.draft(33000)
                prepared = await FactAttachments(engine, self.files).prepare(
                    store,
                    self.access,
                    (draft,),
                )
                # file_id/hash是真的，换事件身份仍必须拒绝，不能借用另一事实的附件。
                forged = replace(prepared, drafts=(replace(prepared.drafts[0], event_id=uuid4()),))
                with self.assertRaisesRegex(ValueError, "not registered"):
                    async with engine.begin() as connection:
                        events = await store.append(
                            connection,
                            self.access,
                            forged,
                            commit_id=uuid4(),
                            correlation_id=uuid4(),
                            expected_seq={("account", self.identity): 0},
                        )
                        await apply_account_events(connection, events)
            finally:
                await engine.dispose()

        asyncio.run(check())

    def test_prepared_inline_body_cannot_be_changed(self) -> None:
        async def check() -> None:
            engine = application_engine(self.app)
            try:
                store = event_store()
                draft = self.draft(300)
                prepared = await FactAttachments(engine, self.files).prepare(
                    store,
                    self.access,
                    (draft,),
                )
                changed = self.draft(301).payload
                forged = replace(prepared, drafts=(replace(prepared.drafts[0], payload=changed),))
                with self.assertRaisesRegex(ValueError, "inline content changed"):
                    async with engine.begin() as connection:
                        events = await store.append(
                            connection,
                            self.access,
                            forged,
                            commit_id=uuid4(),
                            correlation_id=uuid4(),
                            expected_seq={("account", self.identity): 0},
                        )
                        await apply_account_events(connection, events)
            finally:
                await engine.dispose()

        asyncio.run(check())

    def test_concurrent_preparation_reuses_registration(self) -> None:
        async def check() -> None:
            engine = application_engine(self.app)
            try:
                attachments = FactAttachments(engine, self.files)
                draft = self.draft(33000)
                first, second = await asyncio.gather(
                    attachments.prepare(event_store(), self.access, (draft,)),
                    attachments.prepare(event_store(), self.access, (draft,)),
                )
                self.assertEqual(first.drafts, second.drafts)
            finally:
                await engine.dispose()

        asyncio.run(check())
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT count(*) FROM runtime.file_objects")), 1
            )
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM runtime.events")), 1)

    def test_file_registration_is_immutable(self) -> None:
        asyncio.run(self.save(self.draft(33000)))

        async def reject_changes() -> None:
            engine = application_engine(self.app)
            try:
                for sql in (
                    "DELETE FROM runtime.file_objects",
                    "TRUNCATE runtime.file_objects",
                    "UPDATE runtime.file_objects SET sha256=sha256",
                ):
                    with self.assertRaises(DBAPIError):
                        async with engine.begin() as connection:
                            await connection.execute(text(sql))
            finally:
                await engine.dispose()

        asyncio.run(reject_changes())

    def test_actual_pvc_round_trip(self) -> None:
        """独立UUID文件验证真实PVC，清理仅限本用例返回的文件名。"""
        files = LocalFiles(Path(os.environ["M1_TEST_FILES_ROOT"]), backend="pvc")
        saved = files.save(io.BytesIO(b"E01-06 PVC"), max_bytes=11)
        try:
            self.assertEqual(files.read(saved, max_bytes=11), b"E01-06 PVC")
        finally:
            (files.root / saved.storage_key).unlink()
