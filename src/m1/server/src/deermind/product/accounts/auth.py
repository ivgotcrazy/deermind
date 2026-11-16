"""密码登录及可撤销会话；散列在事务外，成功事实与会话共同提交。"""

import asyncio
import hashlib
import logging
import math
import secrets
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import EventDraft, ProducerAccess, Ref
from deermind.foundation.system.events.store import EventStore
from deermind.product.accounts.auth_facts import SIGNED_IN, SIGNED_OUT
from deermind.product.public.authentication import (
    AccountView,
    AuthError,
    LoginResult,
    SessionView,
    UsageGap,
)
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pydantic import JsonValue
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

LOGGER = logging.getLogger("product.auth")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def account_view(row: RowMapping) -> AccountView:
    gaps = []
    if row["role"] == "student":
        reasons = row.get("usage_reasons")
        if row.get("eligibility") == "allowed":
            gaps = []
        elif reasons:
            gaps = [UsageGap.model_validate(item) for item in reasons]
        else:
            gaps = [
                UsageGap(
                    code="usage_confirmation_required",
                    path="account",
                    message="监护及使用确认尚未完成，暂不能进入学习。",
                )
            ]
    return AccountView.model_validate(
        {
            "account_id": row["account_id"],
            "display_name": row["display_name"],
            "role": row["role"],
            "usage_gaps": gaps,
        }
    )


class AuthService:
    """单API最多两个散列任务；跨重启尝试限额及会话由业务PG保存。"""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.hasher = PasswordHash((Argon2Hasher(memory_cost=19456, time_cost=2, parallelism=1),))
        self._hashes = 0
        self._dummy_hash: str | None = None
        self.store = EventStore([SIGNED_IN, SIGNED_OUT])

    async def initialize(self) -> None:
        self._dummy_hash = await asyncio.to_thread(self.hasher.hash, secrets.token_urlsafe(32))

    async def _admit(self, login: str, source: str) -> UUID:
        """锁定限流键后计数并占位，防止并发请求绕过账号失败上限。"""
        identity = uuid4()
        keys = {"login": digest(login), "source": digest(source)}
        refusal: AuthError | None = None
        async with self.engine.begin() as connection:
            for value in sorted("auth:" + key + ":" + val for key, val in keys.items()):
                await connection.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:v,0))"), {"v": value}
                )
            now = await connection.scalar(text("SELECT clock_timestamp()"))
            if not isinstance(now, datetime):
                raise RuntimeError("Database clock unavailable")
            for key, limit in (("login", 5), ("source", 60)):
                condition = "AND outcome IN ('pending','invalid')" if key == "login" else ""
                row = (
                    await connection.execute(
                        text(
                            f"SELECT count(*) AS total,min(admitted_at) AS oldest "
                            "FROM product.login_attempts "
                            f"WHERE {key}_digest=:value AND admitted_at>:since {condition}"
                        ),
                        {"value": keys[key], "since": now - timedelta(minutes=15)},
                    )
                ).one()
                if row.total >= limit:
                    seconds = max(
                        1, math.ceil((row.oldest + timedelta(minutes=15) - now).total_seconds())
                    )
                    refusal = AuthError(
                        429, "too_many_attempts", f"尝试次数过多，请在{seconds}秒后重试。", seconds
                    )
                    break
            if refusal is None:
                await connection.execute(
                    text(
                        "INSERT INTO product.login_attempts "
                        "(attempt_id,login_digest,source_digest,admitted_at,outcome) "
                        "VALUES (:id,:login,:source,:now,'pending')"
                    ),
                    {"id": identity, **keys, "now": now},
                )
        if refusal:
            raise refusal
        return identity

    async def _attempt_result(self, identity: UUID, outcome: str) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE product.login_attempts SET outcome=:outcome "
                    "WHERE attempt_id=:id AND outcome='pending'"
                ),
                {"id": identity, "outcome": outcome},
            )

    async def sign_in(
        self, login: str, password: str, source: str, old_token: str | None
    ) -> LoginResult:
        """旧密码校验不能越过并发重置；换账号只撤销此浏览器旧会话。"""
        login = login.strip().casefold()
        if not login or len(login) > 256 or not 15 <= len(password) <= 128:
            raise AuthError(400, "invalid_request", "请检查账号及密码长度。")
        if self._dummy_hash is None:
            raise RuntimeError("Authentication service is not initialized")
        if self._hashes >= 2:
            raise AuthError(503, "resource_unavailable", "正在处理其他登录，请稍后再试。")
        self._hashes += 1
        attempt: UUID | None = None
        try:
            attempt = await self._admit(login, source)
            async with self.engine.connect() as connection:
                row = (
                    (
                        await connection.execute(
                            text(
                                "SELECT a.*,c.password_hash,c.credential_revision "
                                "FROM product.accounts a "
                                "JOIN product.credentials c USING(account_id) WHERE "
                                "login_identifier=:login"
                            ),
                            {"login": login},
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            password_hash = row["password_hash"] if row else self._dummy_hash
            verification = asyncio.create_task(
                asyncio.to_thread(self.hasher.verify, password, password_hash)
            )
            try:
                valid = await asyncio.shield(verification)
            except asyncio.CancelledError:
                # 线程中的散列不能取消；完成后才释放槽位，避免连续断连绕过上限。
                await verification
                raise
            if not valid or row is None or row["status"] != "active":
                await self._attempt_result(attempt, "invalid")
                raise AuthError(401, "unauthenticated", "账号或密码不正确。")
            result = await self._open_session(row, old_token, attempt)
            LOGGER.info(
                "登录成功",
                extra={"action": "sign_in", "outcome": "success", "request_id": str(attempt)},
            )
            return result
        except AuthError as error:
            if attempt is not None:
                await self._attempt_result(attempt, "unavailable")
            LOGGER.warning(
                "登录未完成",
                extra={"action": "sign_in", "outcome": "rejected", "error_code": error.code},
            )
            raise
        except Exception:
            if attempt is not None:
                await self._attempt_result(attempt, "unavailable")
            raise
        finally:
            self._hashes -= 1

    async def _event(
        self,
        connection: AsyncConnection,
        account: UUID,
        session: UUID,
        outcome: Literal["signed_in", "signed_out", "invalidated"],
        request_id: UUID,
    ) -> None:
        owner = Ref(owner="product", type="account", id=str(account))
        event_type = "AccountSignedIn" if outcome == "signed_in" else "AccountSignedOut"
        payload: dict[str, JsonValue] = {
            "records": [],
            "account_id": str(account),
            "session_id": str(session),
        }
        if outcome != "signed_in":
            payload.update(
                {
                    "subject_ref": owner.model_dump(mode="json"),
                    "outcome": outcome,
                    "reason_code": "account_switch" if outcome == "invalidated" else None,
                }
            )
        seq = await connection.scalar(
            text(
                "SELECT last_seq FROM runtime.scope_event_heads "
                "WHERE scope_kind='account' AND scope_id=:id FOR UPDATE"
            ),
            {"id": account},
        )
        if seq is None:
            raise RuntimeError("Account has no source facts")
        await self.store.append_and_project(
            connection,
            ProducerAccess("product", owner, frozenset({("account", account)})),
            [
                EventDraft(
                    uuid4(), event_type, 1, "account", account, owner, payload, str(request_id)
                )
            ],
            commit_id=request_id,
            correlation_id=request_id,
            expected_seq={("account", account): seq},
        )

    async def _open_session(
        self, original: RowMapping, old_token: str | None, attempt: UUID
    ) -> LoginResult:
        token = secrets.token_urlsafe(32)
        session = uuid4()
        csrf = secrets.token_urlsafe(32)
        async with self.engine.begin() as connection:
            # 先按固定顺序锁账号事件头，再复核凭据；撤销及凭据变更也随事实提交。
            old = (
                (
                    await connection.execute(
                        text(
                            "SELECT session_id,account_id FROM product.auth_sessions "
                            "WHERE token_hash=:hash"
                        ),
                        {"hash": digest(old_token or "")},
                    )
                )
                .mappings()
                .one_or_none()
            )
            ids = sorted({original["account_id"], *([old["account_id"]] if old else [])}, key=str)
            for identity in ids:
                await connection.execute(
                    text(
                        "SELECT last_seq FROM runtime.scope_event_heads "
                        "WHERE scope_kind='account' AND scope_id=:id FOR UPDATE"
                    ),
                    {"id": identity},
                )
            current = (
                (
                    await connection.execute(
                        text(
                            "SELECT a.*,c.credential_revision,c.password_hash,u.eligibility, "
                            "u.reasons AS usage_reasons FROM "
                            "product.accounts a "
                            "JOIN product.credentials c USING(account_id) "
                            "LEFT JOIN product.usage_conditions u "
                            "ON u.student_id=a.account_id WHERE a.account_id=:id"
                        ),
                        {"id": original["account_id"]},
                    )
                )
                .mappings()
                .one()
            )
            if (
                current["status"] != "active"
                or current["credential_revision"] != original["credential_revision"]
                or current["password_hash"] != original["password_hash"]
            ):
                raise AuthError(401, "unauthenticated", "账号或密码已变更，请重新登录。")
            now = await connection.scalar(text("SELECT clock_timestamp()"))
            if not isinstance(now, datetime):
                raise RuntimeError("Database clock unavailable")
            if old:
                changed = await connection.execute(
                    text(
                        "UPDATE product.auth_sessions SET revoked_at=:now "
                        "WHERE session_id=:id AND revoked_at IS NULL"
                    ),
                    {"now": now, "id": old["session_id"]},
                )
                if changed.rowcount:
                    await self._event(
                        connection, old["account_id"], old["session_id"], "invalidated", attempt
                    )
            expires = now + timedelta(hours=24)
            await connection.execute(
                text(
                    "INSERT INTO product.auth_sessions "
                    "(session_id,account_id,token_hash,credential_revision,csrf_token,"
                    "created_at,expires_at) "
                    "VALUES (:session,:account,:hash,:revision,:csrf,:now,:expires)"
                ),
                {
                    "session": session,
                    "account": current["account_id"],
                    "hash": digest(token),
                    "revision": current["credential_revision"],
                    "csrf": csrf,
                    "now": now,
                    "expires": expires,
                },
            )
            await self._event(connection, current["account_id"], session, "signed_in", attempt)
            await connection.execute(
                text("UPDATE product.login_attempts SET outcome='success' WHERE attempt_id=:id"),
                {"id": attempt},
            )
            view = SessionView(
                account=account_view(current),
                session_id=session,
                csrf_token=csrf,
                expires_at=expires,
            )
        return LoginResult(view, token)

    async def session(self, token: str | None, expected: str | None = None) -> SessionView:
        async with self.engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT "
                            "a.account_id,a.display_name,a.role,s.session_id,"
                            "s.csrf_token,s.expires_at,u.eligibility,u.reasons AS usage_reasons "
                            "FROM product.auth_sessions s JOIN product.accounts a "
                            "USING(account_id) "
                            "JOIN product.credentials c USING(account_id) "
                            "LEFT JOIN product.usage_conditions u "
                            "ON u.student_id=a.account_id WHERE s.token_hash=:hash "
                            "AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp() "
                            "AND a.status='active' AND s.credential_revision=c.credential_revision"
                        ),
                        {"hash": digest(token or "")},
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise AuthError(401, "unauthenticated", "请先登录。")
        if expected is not None and expected != str(row["session_id"]):
            raise AuthError(409, "session_changed", "登录账号已变化，请重新确认身份。")
        return SessionView(
            account=account_view(row),
            session_id=row["session_id"],
            csrf_token=row["csrf_token"],
            expires_at=row["expires_at"],
        )

    async def sign_out(self, token: str | None, expected: str | None, csrf: str | None) -> None:
        try:
            view = await self.session(token, expected)
        except AuthError as error:
            if error.status == 401:
                return
            raise
        if expected is None or csrf is None or not secrets.compare_digest(csrf, view.csrf_token):
            raise AuthError(403, "forbidden", "请刷新页面后重试。")
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "SELECT last_seq FROM runtime.scope_event_heads "
                    "WHERE scope_kind='account' AND scope_id=:id FOR UPDATE"
                ),
                {"id": view.account.account_id},
            )
            result = await connection.execute(
                text(
                    "UPDATE product.auth_sessions SET revoked_at=clock_timestamp() "
                    "WHERE session_id=:id AND revoked_at IS NULL"
                ),
                {"id": view.session_id},
            )
            if result.rowcount:
                await self._event(
                    connection, view.account.account_id, view.session_id, "signed_out", uuid4()
                )
        LOGGER.info("登录已退出", extra={"action": "sign_out", "outcome": "success"})
