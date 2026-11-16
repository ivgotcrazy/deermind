"""受控开户与密码恢复；密码散列在事务外，事实、凭据、收据共同提交。"""

import asyncio
from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.events.store import EventStore
from deermind.product.accounts.auth import AuthService
from deermind.product.accounts.conditions import derive_conditions
from deermind.product.accounts.facts import AccountFact, AccountSaved
from deermind.product.accounts.recovery_facts import AccountRecovered
from deermind.product.accounts.save import canonical_actor
from deermind.product.accounts.transactions import (
    append_account_event,
    authorize,
    database_time,
    lock_accounts,
)
from deermind.product.accounts.usage import current_conditions
from deermind.product.accounts.usage_events import record
from deermind.product.accounts.usage_facts import GuardianFact, RelationFact
from deermind.product.persistence.receipts import Receipt, claim_request, complete_request
from deermind.product.public.authentication import AuthError, SessionView
from deermind.product.public.notice import TEST_NOTICE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class AccountManager:
    def __init__(self, engine: AsyncEngine, auth: AuthService, store: EventStore) -> None:
        self.engine, self.auth, self.store = engine, auth, store

    async def _hash(self, password: str) -> str:
        if not 15 <= len(password) <= 128:
            raise AuthError(400, "invalid_request", "密码必须为15–128个字符。")
        return await asyncio.to_thread(self.auth.hasher.hash, password)

    async def update_student(
        self,
        session: SessionView,
        *,
        account_id: UUID,
        request_id: UUID,
        expected_revision: int,
        login: str,
        name: str,
    ) -> Receipt:
        """追加新的资料快照，保留账号身份、监护依据和使用决定。"""
        actor = Ref(owner="product", type="account", id=str(session.account.account_id))
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=canonical_actor(actor),
                action="update_student",
                scope_id=str(account_id),
                request_id=str(request_id),
                normalized_input={
                    "account_id": str(account_id),
                    "revision": expected_revision,
                    "login": login.strip().casefold(),
                    "name": name,
                },
            )
            await lock_accounts(connection, {account_id, session.account.account_id})
            await authorize(connection, session, admin=True)
            if receipt.result_ref is not None:
                return receipt
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT account_id,login_identifier,display_name,"
                            "role,status,revision,created_at FROM product.accounts "
                            "WHERE account_id=:id "
                            "AND role='student'"
                        ),
                        {"id": account_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise AuthError(404, "not_found", "学生账号不存在。")
            original = AccountFact.model_validate(dict(row))
            if original.revision != expected_revision:
                raise AuthError(409, "revision_conflict", "账号已变化，请重新核对。")
            updated = AccountFact.model_validate(
                {
                    **original.model_dump(),
                    "revision": expected_revision + 1,
                    "login_identifier": login.strip().casefold(),
                    "display_name": name,
                }
            )
            conditions = await current_conditions(connection, account_id)
            payload = AccountSaved(
                account_id=account_id,
                action="update_student",
                account_revision=updated.revision,
                relation_refs=[],
                records=[
                    record("account", "product.accounts", updated),
                    record("conditions", "product.usage_conditions", conditions),
                ],
            )
            await append_account_event(
                connection,
                self.store,
                actor=actor,
                account=account_id,
                event_type="TrialAccountSaved",
                payload=payload,
                request_id=str(request_id),
                receipt_id=receipt.request_ref,
                revision=updated.revision,
            )
            return await complete_request(
                connection,
                receipt,
                Ref(owner="product", type="account", id=str(account_id), revision=updated.revision),
            )

    async def bootstrap(self, *, login: str, name: str, password: str, operator: str) -> Receipt:
        """仅持部署凭据的维护入口可用；固定收据唯一键保证安装只引导一次。"""
        hashed = await self._hash(password)
        actor = Ref(owner="runtime", type="maintenance_operator", id=operator)
        async with self.engine.begin() as connection:
            if await connection.scalar(text("SELECT current_user")) != "deermind_migrator":
                raise AuthError(403, "forbidden", "首次管理员必须由部署维护账号创建。")
            receipt = await claim_request(
                connection,
                principal_id="installation",
                action="bootstrap_admin",
                scope_id="installation",
                request_id="bootstrap_admin",
                normalized_input={
                    "login": login.strip().casefold(),
                    "name": name,
                    "operator": operator,
                },
            )
            if receipt.result_ref is not None:
                return receipt
            if await connection.scalar(
                text("SELECT EXISTS(SELECT 1 FROM product.accounts WHERE role='admin')")
            ):
                raise AuthError(409, "already_initialized", "已有管理员，请使用账号恢复命令。")
            now = await database_time(connection)
            account = AccountFact(
                account_id=uuid4(),
                login_identifier=login.strip().casefold(),
                display_name=name,
                role="admin",
                status="active",
                revision=1,
                created_at=now,
            )
            payload = AccountSaved(
                account_id=account.account_id,
                action="bootstrap_admin",
                account_revision=1,
                relation_refs=[],
                records=[record("account", "product.accounts", account)],
            )
            await append_account_event(
                connection,
                self.store,
                actor=actor,
                account=account.account_id,
                event_type="TrialAccountSaved",
                payload=payload,
                request_id="bootstrap_admin",
                receipt_id=receipt.request_ref,
                revision=1,
            )
            await connection.execute(
                text(
                    "INSERT INTO product.credentials "
                    "(account_id,password_hash,credential_revision,changed_at) "
                    "VALUES (:id,:hash,1,:now)"
                ),
                {"id": account.account_id, "hash": hashed, "now": now},
            )
            return await complete_request(
                connection,
                receipt,
                Ref(owner="product", type="account", id=str(account.account_id), revision=1),
            )

    async def create_student(
        self,
        session: SessionView,
        *,
        request_id: UUID,
        login: str,
        name: str,
        password: str,
        guardian_name: str,
        verification_ref: Ref,
        synthetic: bool,
    ) -> Receipt:
        if not synthetic:
            raise AuthError(403, "test_accounts_only", "当前仅允许合成测试账号。")
        if session.account.role != "admin":
            raise AuthError(403, "forbidden", "仅管理员可以创建测试账号。")
        hashed = await self._hash(password)
        actor = Ref(owner="product", type="account", id=str(session.account.account_id))
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=canonical_actor(actor),
                action="create_student",
                scope_id="accounts",
                request_id=str(request_id),
                normalized_input={
                    "login": login.strip().casefold(),
                    "name": name,
                    "guardian_name": guardian_name,
                    "verification_ref": verification_ref.model_dump(mode="json"),
                    "synthetic": True,
                },
            )
            await lock_accounts(connection, {session.account.account_id})
            await authorize(connection, session, admin=True)
            if receipt.result_ref is not None:
                return receipt
            now = await database_time(connection)
            student = AccountFact(
                account_id=uuid4(),
                login_identifier=login.strip().casefold(),
                display_name=name,
                role="student",
                status="active",
                revision=1,
                created_at=now,
            )
            records = [record("account", "product.accounts", student)]
            # 同一核实身份复用监护记录，不根据显示名合并人。唯一约束处理并发冲突。
            guardian = await connection.scalar(
                text(
                    "SELECT guardian_id FROM product.guardian_records "
                    "WHERE verified_identity_ref=CAST(:ref AS jsonb)"
                ),
                {"ref": verification_ref.model_dump_json()},
            )
            if guardian is None:
                guardian = uuid4()
                records.append(
                    record(
                        "guardian",
                        "product.guardian_records",
                        GuardianFact(
                            guardian_id=guardian,
                            verified_identity_ref=verification_ref,
                            display_name=guardian_name,
                            created_at=now,
                        ),
                    )
                )
            relation = RelationFact(
                relation_id=uuid4(),
                student_id=student.account_id,
                guardian_id=guardian,
                revision=1,
                verification_ref=verification_ref,
                relation_state="active",
                previous_relation_id=None,
                actor_ref=actor,
                created_at=now,
            )
            records.append(record("relation", "product.student_guardian_relations", relation))
            conditions = derive_conditions(
                student_id=student.account_id,
                revision=1,
                now=now,
                notice_ref=TEST_NOTICE,
                guardian_verified=True,
                confirmations=[],
            )
            records.append(record("conditions", "product.usage_conditions", conditions))
            payload = AccountSaved(
                account_id=student.account_id,
                action="create_student",
                account_revision=1,
                relation_refs=[
                    Ref(owner="product", type="guardian_relation", id=str(relation.relation_id))
                ],
                records=records,
            )
            await append_account_event(
                connection,
                self.store,
                actor=actor,
                account=student.account_id,
                event_type="TrialAccountSaved",
                payload=payload,
                request_id=str(request_id),
                receipt_id=receipt.request_ref,
                revision=1,
            )
            await connection.execute(
                text(
                    "INSERT INTO product.credentials "
                    "(account_id,password_hash,credential_revision,changed_at) "
                    "VALUES (:id,:hash,1,:now)"
                ),
                {"id": student.account_id, "hash": hashed, "now": now},
            )
            return await complete_request(
                connection,
                receipt,
                Ref(owner="product", type="account", id=str(student.account_id), revision=1),
            )

    async def recover(
        self,
        session: SessionView | None,
        *,
        account_id: UUID,
        request_id: UUID,
        expected_revision: int,
        verification_ref: Ref,
        password: str,
        operator: str | None = None,
    ) -> Receipt:
        """普通管理员恢复学生；部署维护者可恢复管理员。旧会话凭据代次立即失效。"""
        hashed = await self._hash(password)
        actor = (
            Ref(owner="product", type="account", id=str(session.account.account_id))
            if session
            else Ref(owner="runtime", type="maintenance_operator", id=operator or "")
        )
        async with self.engine.begin() as connection:
            receipt = await claim_request(
                connection,
                principal_id=canonical_actor(actor),
                action="recover_account",
                scope_id=str(account_id),
                request_id=str(request_id),
                normalized_input={
                    "account_id": str(account_id),
                    "expected_revision": expected_revision,
                    "verification_ref": verification_ref.model_dump(mode="json"),
                },
            )
            await lock_accounts(
                connection, {account_id, *([session.account.account_id] if session else [])}
            )
            if session:
                await authorize(connection, session, admin=True)
            elif await connection.scalar(text("SELECT current_user")) != "deermind_migrator":
                raise AuthError(403, "forbidden", "维护恢复需要部署凭据。")
            account = (
                (
                    await connection.execute(
                        text("SELECT role,revision FROM product.accounts WHERE account_id=:id"),
                        {"id": account_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if account is None or account["role"] != ("student" if session else "admin"):
                raise AuthError(404, "not_found", "可恢复的账号不存在。")
            if receipt.result_ref is not None:
                return receipt
            if account["revision"] != expected_revision:
                raise AuthError(409, "revision_conflict", "账号已变化，请重新核对。")
            revision = await connection.scalar(
                text(
                    "UPDATE product.credentials SET password_hash=:hash,"
                    "credential_revision=credential_revision+1,changed_at=clock_timestamp() "
                    "WHERE account_id=:id RETURNING credential_revision"
                ),
                {"id": account_id, "hash": hashed},
            )
            if not isinstance(revision, int):
                raise AuthError(404, "not_found", "账号凭据不存在。")
            event = await append_account_event(
                connection,
                self.store,
                actor=actor,
                account=account_id,
                event_type="AccountRecovered",
                schema_version=2,
                payload=AccountRecovered(
                    account_id=account_id,
                    verification_ref=verification_ref,
                    credential_revision=revision,
                    records=[],
                ),
                request_id=str(request_id),
                receipt_id=receipt.request_ref,
            )
            return await complete_request(
                connection, receipt, Ref(owner="runtime", type="event", id=str(event))
            )
