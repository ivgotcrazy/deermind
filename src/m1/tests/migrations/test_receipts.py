"""E01-11真实PG：只读收据、原结果、身份隔离和同键冲突。"""

import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import test_account_usage as usage_fixture
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.public.receipts import ReceiptQuery
from deermind.foundation.system.requests import RequestReceipts
from deermind.product.accounts.auth import AuthService
from deermind.product.accounts.manage import AccountManager
from deermind.product.public.authentication import AuthError, SessionView
from deermind.product.public.errors import RequestConflict
from deermind.product.public.usage import ConfirmationInput, ConfirmUsageRequest, UsageService
from sqlalchemy import text
from test_database import DatabaseTestCase


class ReceiptTests(DatabaseTestCase):
    scenario = usage_fixture.AccountUsageTests.scenario

    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)

    def test_original_result_after_new_decision_and_conflict(self) -> None:
        async def check(
            manager: AccountManager,
            auth: AuthService,
            usage: UsageService,
            admin: SessionView,
            student: UUID,
            directory: Path,
        ) -> None:
            session = (
                await auth.sign_in("student", usage_fixture.PASSWORD, "127.0.0.3", None)
            ).view
            view = await usage.view(session)
            command = ConfirmUsageRequest(
                request_id=uuid4(),
                expected_revision=view.revision,
                confirmation=ConfirmationInput(
                    student_id=student,
                    kind="student_assent",
                    notice_ref=view.notice_ref,
                    source_ref=view.source_ref,
                    decision="declined",
                ),
            )
            query = ReceiptQuery(
                action="product.record_usage_confirmation",
                resource_kind="account",
                resource_id=student,
                request_id=str(command.request_id),
            )
            dispatch = RequestReceipts({(query.action, query.resource_kind): usage.read_receipt})
            empty = await usage.read_receipt(student, session.session_id, query)
            self.assertEqual(empty.receipt_state, "not_found")
            self.assertIsNone(empty.result)
            original = await usage.confirm(session, command)
            # 保存另一条决定，再查旧请求仍得到旧决定，而不是最新条件。
            view = await usage.view(session)
            await usage.confirm(
                session,
                ConfirmUsageRequest(
                    request_id=uuid4(),
                    expected_revision=view.revision,
                    confirmation=command.confirmation.model_copy(
                        update={"decision": "accepted", "source_ref": view.source_ref}
                    ),
                ),
            )
            before = self.count_events()
            for _ in range(2):
                result = await usage.read_receipt(student, session.session_id, query)
                self.assertEqual(result.result, original.result)
                self.assertEqual(result.receipt_ref, original.request_ref)
                self.assertEqual(result.receipt_state, "completed")
                self.assertIsNone(result.execution_ref)
                self.assertEqual(await dispatch.read(student, session.session_id, query), result)
            with self.assertRaises(RequestConflict):
                await usage.confirm(
                    session,
                    command.model_copy(
                        update={
                            "confirmation": command.confirmation.model_copy(
                                update={"decision": "accepted"}
                            )
                        }
                    ),
                )
            self.assertEqual(self.count_events(), before)
            for principal, sid, selected in (
                (admin.account.account_id, admin.session_id, query),
                (student, session.session_id, query.model_copy(update={"resource_id": uuid4()})),
                (student, uuid4(), query),
            ):
                with self.assertRaises(AuthError) as caught:
                    await usage.read_receipt(principal, sid, selected)
                self.assertEqual(caught.exception.status, 404)

        asyncio.run(self.scenario(check))

    def count_events(self) -> int:
        with self.engine.connect() as connection:
            return int(connection.scalar(text("SELECT count(*) FROM runtime.events")) or 0)
