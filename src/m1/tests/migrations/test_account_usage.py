"""E01-10真实PG验证；每例随机测试库，密码和身份均为合成数据。"""

import asyncio
import os
import pty
import select
import subprocess
import sys
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID, uuid4

from deermind.abstractions.events import Ref
from deermind.bootstrap.accounts import configure_account_management, configure_usage
from deermind.bootstrap.projections import account_rebuilder
from deermind.entrypoints.maintenance.database import upgrade
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from deermind.product.accounts.auth import AuthService
from deermind.product.accounts.manage import AccountManager
from deermind.product.public.authentication import AuthError, SessionView
from deermind.product.public.errors import RequestConflict
from deermind.product.public.notice import TEST_NOTICE, assent_source
from deermind.product.public.usage import ConfirmationInput, ConfirmUsageRequest, UsageService
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_database import DatabaseTestCase

PASSWORD = "synthetic-test-password-only"
NEW_PASSWORD = "different-synthetic-password"
VERIFICATION = Ref(owner="product", type="synthetic_verification", id="guardian-fixture")


class AccountUsageTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)

    async def scenario(
        self,
        check: Callable[
            [AccountManager, AuthService, UsageService, SessionView, UUID, Path], Awaitable[None]
        ],
    ) -> None:
        maintenance = application_engine(self.migrator)
        engine = application_engine(self.app)
        try:
            bootstrap, _ = await configure_account_management(maintenance)
            first = await bootstrap.bootstrap(
                login="operator",
                name="Synthetic administrator",
                password=PASSWORD,
                operator="test-maintainer",
            )
            again = await bootstrap.bootstrap(
                login="operator",
                name="Synthetic administrator",
                password=NEW_PASSWORD,
                operator="test-maintainer",
            )
            self.assertEqual(first, again)
            with self.assertRaises(RequestConflict):
                await bootstrap.bootstrap(
                    login="other", name="Other", password=PASSWORD, operator="test-maintainer"
                )
            manager, auth = await configure_account_management(engine)
            login = await auth.sign_in("operator", PASSWORD, "127.0.0.1", None)
            request = uuid4()
            created = await manager.create_student(
                login.view,
                request_id=request,
                login="student",
                name="Synthetic student",
                password=PASSWORD,
                guardian_name="Synthetic guardian",
                verification_ref=VERIFICATION,
                synthetic=True,
            )
            repeated = await manager.create_student(
                login.view,
                request_id=request,
                login="student",
                name="Synthetic student",
                password=NEW_PASSWORD,
                guardian_name="Synthetic guardian",
                verification_ref=VERIFICATION,
                synthetic=True,
            )
            self.assertEqual(created, repeated)
            assert created.result_ref is not None
            with tempfile.TemporaryDirectory() as directory:
                await check(
                    manager,
                    auth,
                    configure_usage(engine, Path(directory)),
                    login.view,
                    UUID(created.result_ref.id),
                    Path(directory),
                )
        finally:
            await engine.dispose()
            await maintenance.dispose()

    def test_confirmations_replay_and_permissions(self) -> None:
        async def check(
            manager: AccountManager,
            auth: AuthService,
            usage: UsageService,
            admin: SessionView,
            student: UUID,
            directory: Path,
        ) -> None:
            signed_in = await auth.sign_in("student", PASSWORD, "127.0.0.2", None)
            self.assertEqual(len(signed_in.view.account.usage_gaps), 2)
            before = await usage.view(signed_in.view)
            self.assertFalse(before.allowed)
            with self.assertRaises(AuthError):
                await manager.create_student(
                    signed_in.view,
                    request_id=uuid4(),
                    login="evil",
                    name="No",
                    password=PASSWORD,
                    guardian_name="No",
                    verification_ref=VERIFICATION,
                    synthetic=True,
                )
            with self.assertRaises(AuthError):
                await manager.create_student(
                    admin,
                    request_id=uuid4(),
                    login="real",
                    name="No",
                    password=PASSWORD,
                    guardian_name="No",
                    verification_ref=VERIFICATION,
                    synthetic=False,
                )
            guardian = ConfirmUsageRequest(
                request_id=uuid4(),
                expected_revision=1,
                confirmation=ConfirmationInput(
                    student_id=student,
                    kind="guardian_consent",
                    notice_ref=TEST_NOTICE,
                    decision="accepted",
                    source_ref=VERIFICATION,
                ),
            )
            with self.assertRaises(AuthError):
                await usage.confirm(signed_in.view, guardian)
            first = await usage.confirm(admin, guardian)
            self.assertFalse(first.result.allowed)
            self.assertEqual(first, await usage.confirm(admin, guardian))
            assent = ConfirmUsageRequest(
                request_id=uuid4(),
                expected_revision=2,
                confirmation=ConfirmationInput(
                    student_id=student,
                    kind="student_assent",
                    notice_ref=TEST_NOTICE,
                    decision="accepted",
                    source_ref=assent_source(str(student), 2),
                ),
            )
            final = await usage.confirm(signed_in.view, assent)
            self.assertTrue(final.result.allowed)
            self.assertEqual(final, await usage.confirm(signed_in.view, assent))
            # 后来的本人确认不改变先前监护请求返回的原条件快照。
            self.assertEqual(first, await usage.confirm(admin, guardian))
            self.assertEqual((await auth.session(signed_in.token)).account.usage_gaps, [])
            with self.assertRaises(AuthError):
                await usage.confirm(
                    signed_in.view, assent.model_copy(update={"request_id": uuid4()})
                )
            with self.engine.connect() as connection:
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM product.usage_confirmations")), 2
                )
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM product.guardian_records")), 1
                )
                self.assertEqual(
                    connection.scalar(
                        text(
                            "SELECT min(schema_version) FROM runtime.events "
                            "WHERE event_type='UsageConfirmationRecorded'"
                        )
                    ),
                    2,
                )
                content = str(connection.execute(text("SELECT payload FROM runtime.events")).all())
                receipts = str(
                    connection.execute(
                        text("SELECT normalized_input FROM product.command_receipt")
                    ).all()
                )
                for secret in (
                    PASSWORD,
                    NEW_PASSWORD,
                    "$argon2id$",
                    signed_in.token,
                    signed_in.view.csrf_token,
                ):
                    self.assertNotIn(secret, content + receipts)

            # 两条确认属于同一账号；调换结果引用后也不能冒充原请求。
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE product.command_receipt SET result_ref=jsonb_set("
                        "result_ref, '{id}', (SELECT to_jsonb(event_id::text) FROM runtime.events "
                        "WHERE correlation_id=:other AND event_type='UsageConfirmationRecorded')) "
                        "WHERE request_ref=:original"
                    ),
                    {"other": first.request_ref, "original": final.request_ref},
                )
            with self.assertRaises(AuthError):
                await usage.confirm(signed_in.view, assent)

        asyncio.run(self.scenario(check))

    def test_decline_concurrency_and_transaction_rollback(self) -> None:
        async def check(
            manager: AccountManager,
            auth: AuthService,
            usage: UsageService,
            admin: SessionView,
            student: UUID,
            directory: Path,
        ) -> None:
            signed_in = await auth.sign_in("student", PASSWORD, "127.0.0.2", None)
            command = ConfirmUsageRequest(
                request_id=uuid4(),
                expected_revision=1,
                confirmation=ConfirmationInput(
                    student_id=student,
                    kind="student_assent",
                    notice_ref=TEST_NOTICE,
                    decision="declined",
                    source_ref=assent_source(str(student), 1),
                ),
            )
            results = await asyncio.gather(
                usage.confirm(signed_in.view, command), usage.confirm(signed_in.view, command)
            )
            self.assertEqual(results[0], results[1])
            self.assertFalse(results[0].result.allowed)
            self.assertIn("student_assent_declined", [r.code for r in results[0].result.gaps])
            with self.engine.connect() as connection:
                count = connection.scalar(text("SELECT count(*) FROM runtime.events"))
            with self.assertRaises(IntegrityError):
                await manager.create_student(
                    admin,
                    request_id=uuid4(),
                    login="student",
                    name="Duplicate",
                    password=PASSWORD,
                    guardian_name="Another",
                    verification_ref=VERIFICATION,
                    synthetic=True,
                )
            with self.engine.connect() as connection:
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM runtime.events")), count
                )
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM product.accounts")), 2
                )
                self.assertEqual(
                    connection.scalar(text("SELECT count(*) FROM product.usage_confirmations")), 1
                )

        asyncio.run(self.scenario(check))

    def test_recovery_and_update_preserve_identity(self) -> None:
        async def check(
            manager: AccountManager,
            auth: AuthService,
            usage: UsageService,
            admin: SessionView,
            student: UUID,
            directory: Path,
        ) -> None:
            old = await auth.sign_in("student", PASSWORD, "127.0.0.2", None)
            request = uuid4()
            first = await manager.recover(
                admin,
                account_id=student,
                request_id=request,
                expected_revision=1,
                verification_ref=VERIFICATION,
                password=NEW_PASSWORD,
            )
            repeated = await manager.recover(
                admin,
                account_id=student,
                request_id=request,
                expected_revision=1,
                verification_ref=VERIFICATION,
                password=PASSWORD,
            )
            self.assertEqual(first, repeated)
            with self.assertRaises(AuthError):
                await auth.session(old.token)
            with self.assertRaises(AuthError):
                await auth.sign_in("student", PASSWORD, "127.0.0.2", None)
            current = await auth.sign_in("student", NEW_PASSWORD, "127.0.0.2", None)
            self.assertEqual(current.view.account.account_id, student)
            await manager.update_student(
                admin,
                account_id=student,
                request_id=uuid4(),
                expected_revision=1,
                login="renamed",
                name="Updated synthetic student",
            )
            view = await auth.session(current.token)
            self.assertEqual(view.account.display_name, "Updated synthetic student")
            self.assertEqual(len(view.account.usage_gaps), 2)
            # 查询投影可恢复到新资料，但不能恢复旧密码或旧登录。
            maintenance = application_engine(self.migrator)
            try:
                rebuilder = account_rebuilder(maintenance, LocalFiles(directory, backend="local"))
                # 与E01-08相同受控维护入口，在测试库中重建一个账号。
                restored = await rebuilder.rebuild(
                    uuid4(), 2, [student], operator="usage-test", authorization="test-maintenance"
                )
                self.assertEqual(restored.state, "completed")
            finally:
                await maintenance.dispose()
            self.assertEqual(
                (await auth.session(current.token)).account.display_name,
                "Updated synthetic student",
            )
            with self.assertRaises(AuthError):
                await auth.session(old.token)
            with self.engine.connect() as connection:
                self.assertEqual(
                    connection.scalar(
                        text(
                            "SELECT credential_revision FROM product.credentials "
                            "WHERE account_id=:id"
                        ),
                        {"id": student},
                    ),
                    2,
                )
                self.assertEqual(
                    connection.scalar(
                        text(
                            "SELECT min(schema_version) FROM runtime.events "
                            "WHERE event_type='AccountRecovered'"
                        )
                    ),
                    2,
                )
                self.assertEqual(
                    connection.scalar(
                        text("SELECT count(*) FROM product.student_guardian_relations")
                    ),
                    1,
                )

        asyncio.run(self.scenario(check))

    def test_management_command_hides_password_and_resets_session(self) -> None:
        async def check(
            manager: AccountManager,
            auth: AuthService,
            usage: UsageService,
            admin: SessionView,
            student: UUID,
            directory: Path,
        ) -> None:
            login = await auth.sign_in("student", PASSWORD, "127.0.0.2", None)
            await asyncio.to_thread(self.run_reset_command, student)
            with self.assertRaises(AuthError):
                await auth.session(login.token)
            restored = await auth.sign_in("student", NEW_PASSWORD, "127.0.0.2", None)
            self.assertEqual(restored.view.account.account_id, student)

        asyncio.run(self.scenario(check))

    def run_reset_command(self, student: UUID) -> None:
        """真实子进程和终端；密码通过隐藏提示输入，不进入argv或测试输出。"""
        environment = {
            **os.environ,
            "M1_DB_NAME": self.name,
            "M1_DB_USER": "deermind_app",
            "M1_DB_PASSWORD": str(self.app.password),
        }
        master, slave = pty.openpty()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "deermind.entrypoints.maintenance.accounts",
                "reset-student-password",
                "--admin",
                "operator",
                "--request-id",
                str(uuid4()),
                "--account-id",
                str(student),
                "--expected-revision",
                "1",
                "--verification",
                "test-record",
            ],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=environment,
        )
        os.close(slave)
        output = b""
        try:
            for prompt, value in (
                ("管理员密码：", PASSWORD),
                ("新密码：", NEW_PASSWORD),
                ("再次输入密码：", NEW_PASSWORD),
            ):
                while prompt.encode() not in output:
                    ready, _, _ = select.select([master], [], [], 60)
                    self.assertTrue(ready, "Management command did not reach its next prompt")
                    chunk = os.read(master, 65536)
                    self.assertTrue(chunk, "Management command closed before password input")
                    output += chunk
                os.write(master, (value + "\n").encode())
            process.wait(timeout=60)
            while select.select([master], [], [], 0)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
            self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
            self.assertIn("已保存。".encode(), output)
            self.assertNotIn(PASSWORD.encode(), output)
            self.assertNotIn(NEW_PASSWORD.encode(), output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            os.close(master)
