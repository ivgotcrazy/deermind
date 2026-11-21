"""真实PG验证隔离重建；仅随机测试库，不重放正常业务处理器。"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from account_projection_fixture import student_facts
from deermind.abstractions.events import EventDraft, ProducerAccess, Ref
from deermind.bootstrap.events import event_store
from deermind.bootstrap.projections import account_rebuilder
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.projections.contracts import CheckIssue, RebuildJob
from deermind.infrastructure.database.connection import MAINTENANCE_LOCK, application_engine
from deermind.infrastructure.files.local import LocalFiles
from deermind.product.accounts.facts import AccountFact
from deermind.product.accounts.projections import TABLES, apply_account_events
from deermind.product.accounts.rebuild import AccountRebuilder
from deermind.product.accounts.save import save_initial_account
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from test_database import DatabaseTestCase


class InterruptedMaintenance(BaseException):
    """模拟进程退出，不走正常的失败留痕分支。"""


class ProjectionRebuildTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.files = LocalFiles(Path(temporary.name), backend="local")
        self.operator = "test-operator"
        self.authorization = "approved-test-maintenance"

    async def execute(
        self, scenario: Callable[[AsyncEngine, AsyncEngine], Awaitable[None]]
    ) -> None:
        app = application_engine(self.app)
        maintenance = create_async_engine(self.migrator, poolclass=NullPool, hide_parameters=True)
        try:
            await scenario(app, maintenance)
        finally:
            await app.dispose()
            await maintenance.dispose()

    async def seed(self, app: AsyncEngine, *, large: bool = False) -> UUID:
        identity = uuid4()
        access = ProducerAccess(
            "product",
            Ref(owner="runtime", type="service", id="test"),
            frozenset({("account", identity)}),
        )
        if not large:
            await save_initial_account(
                app,
                event_store(),
                access,
                request_id=str(identity),
                account_id=identity,
                login_identifier=identity.hex,
                display_name="原始账号",
            )
            return identity
        fact = AccountFact(
            account_id=identity,
            login_identifier=identity.hex,
            display_name="x" * 33000,
            role="admin",
            status="active",
            revision=1,
            created_at=datetime.now(UTC),
        )
        draft = EventDraft(
            uuid4(),
            "TrialAccountSaved",
            1,
            "account",
            identity,
            Ref(owner="product", type="account", id=str(identity), revision=1),
            {
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
            str(identity),
        )
        store = event_store()
        prepared = await FactAttachments(app, self.files).prepare(store, access, (draft,))
        async with app.begin() as connection:
            events = await store.append(
                connection,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=uuid4(),
                expected_seq={("account", identity): 0},
            )
            await apply_account_events(connection, events)
        return identity

    def rows(self, table: str) -> list[dict[str, object]]:
        # 表名只来自测试代码或程序生成的UUID副本名，不接受外部输入。
        with self.engine.connect() as connection:
            return [
                dict(row) for row in connection.execute(text(f"SELECT * FROM {table}")).mappings()
            ]

    async def rebuild(
        self,
        service: AccountRebuilder,
        scopes: list[UUID],
        generation: int = 2,
        *,
        identity: UUID | None = None,
    ) -> RebuildJob:
        return await service.rebuild(
            identity or uuid4(),
            generation,
            scopes,
            operator=self.operator,
            authorization=self.authorization,
        )

    def assert_no_copy(self, service: AccountRebuilder, identity: UUID) -> None:
        with self.engine.connect() as connection:
            self.assertIsNone(
                connection.scalar(
                    text("SELECT to_regclass(:name)"), {"name": service.stage_name(identity)}
                )
            )

    def test_deleted_projection_restored_and_repeated_generations_are_safe(self) -> None:
        asyncio.run(self.execute(self.round_trip))

    async def round_trip(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scopes = [await self.seed(app) for _ in range(3)]
        before = self.rows("product.accounts")
        requests = self.rows("product.command_receipt")
        original_events = self.rows("runtime.events")
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM product.accounts"))
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, scopes)
        self.assertEqual(job.state, "completed")
        self.assertCountEqual(self.rows("product.accounts"), before)
        self.assertEqual(self.rows("product.command_receipt"), requests)
        self.assertEqual(
            await self.rebuild(service, list(reversed(scopes)), identity=job.rebuild_id), job
        )
        events = self.rows("runtime.events")
        self.assertCountEqual(
            [e for e in events if e["event_type"] == "TrialAccountSaved"], original_events
        )
        self.assertEqual(len(events), len(original_events) + 1)
        self.assert_no_copy(service, job.rebuild_id)
        self.assertEqual((await self.rebuild(service, scopes, 3)).state, "completed")
        self.assertCountEqual(self.rows("product.accounts"), before)
        receipts = self.rows("runtime.projection_receipts")
        online = [
            r
            for r in receipts
            if r["projector_id"] == "product.account_views.v2" and r["generation"] == 1
        ]
        self.assertEqual(len(online), 3)
        self.assertTrue(
            all(
                r["state"] == "live"
                for r in self.rows("runtime.projection_offsets")
                if r["generation"] == 1
            )
        )
        self.assertEqual(
            {e["event_type"] for e in self.rows("runtime.events")},
            {"TrialAccountSaved", "ProjectionRebuildFinished"},
        )

    def test_interruption_rolls_back_publication_and_new_run_restarts(self) -> None:
        asyncio.run(self.execute(self.interruption))

    async def interruption(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app)
        before = self.rows("product.accounts")
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM product.accounts"))
        service = account_rebuilder(maintenance, self.files)
        identity = uuid4()
        publish = service.records.publish

        async def interrupt_after_writes(
            gate: AsyncConnection, job: RebuildJob, checks: list[CheckIssue]
        ) -> None:
            await publish(gate, job, checks)
            raise InterruptedMaintenance()

        # 正式替换和成功事件都已写入，但事务尚未提交。
        with (
            patch.object(service.records, "publish", side_effect=interrupt_after_writes),
            self.assertRaises(InterruptedMaintenance),
        ):
            await self.rebuild(service, [scope], identity=identity)
        self.assertEqual(self.rows("product.accounts"), [])
        self.assertEqual(self.rows("runtime.projection_rebuilds"), [])
        self.assertEqual(self.rows("runtime.projection_offsets"), [])
        self.assertEqual(len(self.rows("runtime.events")), 1)
        self.assert_no_copy(service, identity)
        self.assertEqual((await self.rebuild(service, [scope], 3)).state, "completed")
        self.assertEqual(self.rows("product.accounts"), before)

    def test_corrupted_stage_fails_without_replacing_online_rows(self) -> None:
        asyncio.run(self.execute(self.corrupt_stage))

    async def corrupt_stage(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app)
        before = self.rows("product.accounts")
        service = account_rebuilder(maintenance, self.files)
        applied = service.records.applied

        async def corrupt(gate: AsyncConnection, job: RebuildJob) -> set[UUID]:
            stage = service.stage_name(job.rebuild_id)
            await gate.execute(text(f"UPDATE {stage} SET display_name='wrong'"))
            return await applied(gate, job)

        with patch.object(service.records, "applied", side_effect=corrupt):
            failed = await self.rebuild(service, [scope])
        self.assertEqual(failed.state, "failed")
        self.assert_no_copy(service, failed.rebuild_id)
        self.assertEqual(self.rows("product.accounts"), before)
        self.assertEqual(await self.rebuild(service, [scope], identity=failed.rebuild_id), failed)
        self.assertEqual(len(self.rows("runtime.events")), 2)
        self.assertEqual((await self.rebuild(service, [scope], 3)).state, "completed")

    def test_generation_failure_rolls_back_copy_and_receipts(self) -> None:
        asyncio.run(self.execute(self.generation_failure))

    async def generation_failure(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app)
        before = self.rows("product.accounts")
        service = account_rebuilder(maintenance, self.files)
        with self.engine.begin() as connection:
            connection.execute(
                text("""
                CREATE FUNCTION runtime.fail_rebuild_receipt() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN IF NEW.generation=2 THEN RAISE EXCEPTION 'test interruption'; END IF;
                RETURN NEW; END $$
            """)
            )
            connection.execute(
                text("""
                CREATE TRIGGER fail_rebuild_receipt BEFORE INSERT ON runtime.projection_receipts
                FOR EACH ROW EXECUTE FUNCTION runtime.fail_rebuild_receipt()
            """)
            )
        job = await self.rebuild(service, [scope])
        self.assertEqual(job.state, "failed")
        self.assert_no_copy(service, job.rebuild_id)
        self.assertFalse(
            any(r["generation"] == 2 for r in self.rows("runtime.projection_receipts"))
        )
        self.assertEqual(self.rows("runtime.projection_offsets"), [])
        self.assertEqual(self.rows("product.accounts"), before)

    def test_final_constraint_failure_preserves_all_online_data(self) -> None:
        asyncio.run(self.execute(self.final_failure))

    async def final_failure(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        target, outside = await self.seed(app), await self.seed(app)
        with self.engine.begin() as connection:
            connection.execute(
                text("UPDATE product.accounts SET login_identifier='changed' WHERE account_id=:id"),
                {"id": target},
            )
            connection.execute(
                text("UPDATE product.accounts SET login_identifier=:login WHERE account_id=:id"),
                {"id": outside, "login": target.hex},
            )
        before = self.rows("product.accounts")
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [target])
        self.assertEqual(job.state, "failed")
        self.assertCountEqual(self.rows("product.accounts"), before)
        self.assertFalse(any(r["generation"] == 1 for r in self.rows("runtime.projection_offsets")))

    def test_saved_result_requires_same_parameters_and_authorization(self) -> None:
        asyncio.run(self.execute(self.fixed_parameters))

    async def fixed_parameters(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        target, outside = await self.seed(app), await self.seed(app)
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [target])
        with self.assertRaises(ValueError):
            await self.rebuild(service, [outside], identity=job.rebuild_id)
        with self.assertRaises(PermissionError):
            await service.status(job.rebuild_id, operator="other", authorization=self.authorization)
        self.assertEqual(
            await service.status(
                job.rebuild_id, operator=self.operator, authorization=self.authorization
            ),
            job,
        )
        self.assertEqual(len(self.rows("runtime.events")), 3)

    def test_missing_source_event_fails_without_publication(self) -> None:
        asyncio.run(self.execute(self.missing_source))

    async def missing_source(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE runtime.scope_event_heads SET last_seq=last_seq+1"))
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [scope])
        self.assertEqual(job.state, "failed")
        self.assert_no_copy(service, job.rebuild_id)
        self.assertEqual(self.rows("runtime.projection_offsets"), [])

    def test_application_identity_and_competing_maintenance_are_rejected(self) -> None:
        asyncio.run(self.execute(self.permissions))

    async def permissions(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app)
        unprivileged = account_rebuilder(app, self.files)
        with self.assertRaises(PermissionError):
            await self.rebuild(unprivileged, [scope])
        for table in ("runtime.projection_rebuilds", "runtime.projection_offsets"):
            with self.assertRaises(DBAPIError):
                async with app.begin() as connection:
                    await connection.execute(text(f"SELECT * FROM {table}"))
        service = account_rebuilder(maintenance, self.files)
        with self.engine.begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": MAINTENANCE_LOCK}
            )
            with self.assertRaises(RuntimeError):
                await self.rebuild(service, [scope])
        self.assertEqual(self.rows("runtime.projection_rebuilds"), [])

    def test_broken_fact_attachment_fails_without_empty_projection(self) -> None:
        asyncio.run(self.execute(self.attachment_failure))

    async def attachment_failure(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app, large=True)
        before = self.rows("product.accounts")
        file_rows = self.rows("runtime.file_objects")
        path = next(self.files.root.glob("*.blob"))
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b"!" + original[1:])
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [scope])
        self.assertEqual(job.state, "failed")
        self.assertEqual(self.rows("product.accounts"), before)
        self.assertEqual(self.rows("runtime.file_objects"), file_rows)
        path.write_bytes(original)
        self.assertEqual((await self.rebuild(service, [scope], 3)).state, "completed")

    def test_cli_requires_maintenance_and_status_reads_committed_result(self) -> None:
        scopes: list[UUID] = []

        async def seed_one(app: AsyncEngine, maintenance: AsyncEngine) -> None:
            scopes.append(await self.seed(app))

        asyncio.run(self.execute(seed_one))
        environment = {
            **os.environ,
            "M1_DB_USER": "deermind_migrator",
            "M1_DB_NAME": self.name,
            "M1_DB_PASSWORD": os.environ["M1_TEST_MIGRATION_PASSWORD"],
            "M1_FILES_ROOT": str(self.files.root),
            "M1_FILES_BACKEND": "local",
        }
        identity = uuid4()
        common = [
            "--rebuild-id",
            str(identity),
            "--operator",
            self.operator,
            "--authorization",
            self.authorization,
        ]
        prefix = [sys.executable, "-m", "deermind.entrypoints.maintenance.rebuild"]
        rejected = subprocess.run(
            prefix + ["status"] + common,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(rejected.returncode, 0)
        record: dict[str, object] = {}
        for action, extra in (
            ("run", ["--generation", "2", "--scope", str(scopes[0])]),
            ("status", []),
        ):
            result = subprocess.run(
                prefix + [action] + common + ["--maintenance-confirmed"] + extra,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(record["rebuild_id"], str(identity))
            self.assertEqual(record["state"], "completed")

    def test_active_writer_blocks_maintenance_without_waiting(self) -> None:
        asyncio.run(self.execute(self.active_writer))

    async def active_writer(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app)
        service = account_rebuilder(maintenance, self.files)
        with self.engine.begin() as connection:
            connection.execute(text("LOCK TABLE runtime.events IN ROW EXCLUSIVE MODE"))
            with self.assertRaises(DBAPIError):
                await self.rebuild(service, [scope])
        self.assertEqual(self.rows("runtime.projection_rebuilds"), [])

    def test_selected_scope_does_not_overwrite_other_accounts(self) -> None:
        asyncio.run(self.execute(self.selected_scope))

    async def selected_scope(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        target, outside = await self.seed(app), await self.seed(app)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE product.accounts SET display_name='query-copy'"))
        service = account_rebuilder(maintenance, self.files)
        self.assertEqual((await self.rebuild(service, [target])).state, "completed")
        # 第二批出错不能改第一批已提交的结果，也不能发布第二批。
        with patch.object(service, "_verify", side_effect=ValueError("batch failed")):
            self.assertEqual((await self.rebuild(service, [outside], 3)).state, "failed")
        rows = {row["account_id"]: row for row in self.rows("product.accounts")}
        self.assertEqual(rows[target]["display_name"], "原始账号")
        self.assertEqual(rows[outside]["display_name"], "query-copy")

    def test_result_failure_rolls_back_online_rows_receipts_and_offsets(self) -> None:
        asyncio.run(self.execute(self.result_failure))

    async def result_failure(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        scope = await self.seed(app)
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM product.accounts"))
            connection.execute(text("DELETE FROM runtime.projection_receipts"))
            connection.execute(
                text("""
                CREATE FUNCTION runtime.fail_completed_result() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN IF NEW.event_type='ProjectionRebuildFinished'
                  AND NEW.payload->>'outcome'='completed'
                  THEN RAISE EXCEPTION 'test final commit failure'; END IF;
                RETURN NEW; END $$
            """)
            )
            connection.execute(
                text("""
                CREATE TRIGGER fail_completed_result BEFORE INSERT ON runtime.events
                FOR EACH ROW EXECUTE FUNCTION runtime.fail_completed_result()
            """)
            )
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [scope])
        self.assertEqual(job.state, "failed")
        self.assertEqual(self.rows("product.accounts"), [])
        self.assertFalse(any(r["generation"] == 1 for r in self.rows("runtime.projection_offsets")))
        receipts = self.rows("runtime.projection_receipts")
        self.assertFalse(
            any(
                r["generation"] == 1 and r["projector_id"] == "product.account_views.v2"
                for r in receipts
            )
        )
        self.assert_no_copy(service, job.rebuild_id)
        results = [
            e for e in self.rows("runtime.events") if e["event_type"] == "ProjectionRebuildFinished"
        ]
        self.assertEqual(len(results), 1)
        self.assertEqual(json.loads(json.dumps(results[0]["payload"]))["outcome"], "failed")

    def test_full_account_history_restores_many_rows_and_current_conditions(self) -> None:
        """同范围多事件、多表、多行均恢复；共享监护人及范围外账号保持有效。"""
        asyncio.run(self.execute(self.full_history))

    async def full_history(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        selected, events = await student_facts(app)
        guardian = self.rows("product.guardian_records")[0]["guardian_id"]
        assert isinstance(guardian, UUID)
        outside, _ = await student_facts(app, guardian=guardian)
        expected = {table.name: self.rows(table.name) for table in TABLES}
        # 重复交付不重写条件，也不重复插入两段关系或确认。
        async with app.begin() as connection:
            await apply_account_events(connection, events)
        for table in TABLES:
            self.assertCountEqual(self.rows(table.name), expected[table.name])
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM product.usage_conditions WHERE student_id=:id"), {"id": selected}
            )
            connection.execute(
                text("DELETE FROM product.usage_confirmations WHERE student_id=:id"),
                {"id": selected},
            )
            connection.execute(
                text("DELETE FROM product.student_guardian_relations WHERE student_id=:id"),
                {"id": selected},
            )
            connection.execute(
                text("UPDATE product.accounts SET display_name='broken' WHERE account_id=:id"),
                {"id": selected},
            )
        service = account_rebuilder(maintenance, self.files)
        self.assertEqual((await self.rebuild(service, [selected])).state, "completed")
        for table in TABLES:
            self.assertCountEqual(self.rows(table.name), expected[table.name])
        conditions = {r["student_id"]: r for r in self.rows("product.usage_conditions")}
        self.assertEqual(conditions[selected]["revision"], 3)
        self.assertEqual(conditions[outside]["eligibility"], "allowed")
        # 另一学生的依赖事实不在本次范围时，必须拒绝而不是偷偷跨范围读写。
        self.assertEqual((await self.rebuild(service, [outside], 3)).state, "failed")
        for table in TABLES:
            self.assertCountEqual(self.rows(table.name), expected[table.name])

    def test_event_save_does_not_apply_business_projection(self) -> None:
        """事件可先独立保存；消费方直接调用同一业务生成器才生成查询数据。"""
        asyncio.run(self.execute(self.explicit_projection))

    async def explicit_projection(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        selected, events = await student_facts(app, project=False)
        self.assertEqual(len(self.rows("runtime.events")), 3)
        self.assertEqual(self.rows("runtime.projection_receipts"), [])
        for table in TABLES:
            self.assertEqual(self.rows(table.name), [])
        # 这是业务订阅处理器的事务；不改变底座的可靠交接/Ack规则。
        async with app.begin() as connection:
            await apply_account_events(connection, events)
        before = {t.name: self.rows(t.name) for t in TABLES}
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [selected])
        self.assertEqual(job.state, "completed")
        for table in TABLES:
            self.assertCountEqual(self.rows(table.name), before[table.name])

    def test_multitable_failure_rolls_back_all_rows_and_receipts(self) -> None:
        asyncio.run(self.execute(self.multitable_failure))

    async def multitable_failure(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE product.usage_conditions ADD CHECK (revision<1)"))
        with self.assertRaises(DBAPIError):
            await student_facts(app)
        self.assertEqual(self.rows("runtime.events"), [])
        self.assertEqual(self.rows("runtime.projection_receipts"), [])
        for table in TABLES:
            self.assertEqual(self.rows(table.name), [])

    def test_extra_owned_rows_removed_but_controls_preserved(self) -> None:
        asyncio.run(self.execute(self.extra_owned_rows))

    async def extra_owned_rows(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        selected, _ = await student_facts(app)
        before = {t.name: self.rows(t.name) for t in TABLES}
        with self.engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO product.usage_confirmations
                SELECT :id,student_id,kind,notice_ref,decision,source_ref,actor_ref,
                       occurred_at,created_at,source_event_id
                FROM product.usage_confirmations LIMIT 1
            """),
                {"id": uuid4()},
            )
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [selected])
        self.assertEqual(job.state, "completed")
        for table in TABLES:
            self.assertCountEqual(self.rows(table.name), before[table.name])

    def test_read_failure_then_new_batch_completes(self) -> None:
        asyncio.run(self.execute(self.temporary_failure))

    async def temporary_failure(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        selected = await self.seed(app)
        service = account_rebuilder(maintenance, self.files)
        with patch.object(
            service.reader, "read_projection_event", side_effect=ConnectionError("temporary")
        ):
            failed = await self.rebuild(service, [selected])
        self.assertEqual(failed.state, "failed")
        self.assert_no_copy(service, failed.rebuild_id)
        self.assertEqual((await self.rebuild(service, [selected], 3)).state, "completed")

    def test_legacy_unfinished_record_remains_readable(self) -> None:
        asyncio.run(self.execute(self.legacy_record))

    async def legacy_record(self, app: AsyncEngine, maintenance: AsyncEngine) -> None:
        selected = await self.seed(app)
        service = account_rebuilder(maintenance, self.files)
        job = await self.rebuild(service, [selected])
        with self.engine.begin() as connection:
            connection.execute(
                text("""
                UPDATE runtime.projection_rebuilds
                SET state='building',result_event_id=NULL
                WHERE rebuild_id=:id
                """),
                {"id": job.rebuild_id},
            )
        old = await service.status(
            job.rebuild_id, operator=self.operator, authorization=self.authorization
        )
        self.assertEqual(old.state, "building")
        with self.assertRaisesRegex(ValueError, "Legacy unfinished"):
            await self.rebuild(service, [selected], identity=job.rebuild_id)
