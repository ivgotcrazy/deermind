"""账号变更的短事务支持；锁顺序与登录、退出保持一致。"""

from datetime import datetime
from uuid import UUID, uuid4

from deermind.abstractions.events import EventDraft, EventPayload, ProducerAccess, Ref
from deermind.foundation.system.events.store import EventStore
from deermind.product.accounts.projections import apply_account_events
from deermind.product.public.authentication import AuthError, SessionView
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def lock_accounts(connection: AsyncConnection, ids: set[UUID]) -> None:
    for identity in sorted(ids, key=str):
        # 按编号排序加锁，保证跨账号锁顺序一致，避免死锁。
        await connection.execute(
            text(
                "SELECT last_seq FROM runtime.scope_event_heads "
                "WHERE scope_kind='account' AND scope_id=:id FOR UPDATE"
            ),
            {"id": identity},
        )


async def authorize(connection: AsyncConnection, session: SessionView, *, admin: bool) -> None:
    """持锁后重新核对会话，防止入口检查后账号被禁用或密码被重置。"""
    valid = await connection.scalar(
        text(
            "SELECT a.role FROM product.auth_sessions s JOIN product.accounts a USING(account_id) "
            "JOIN product.credentials c USING(account_id) WHERE s.session_id=:session "
            "AND a.account_id=:account AND a.status='active' AND s.revoked_at IS NULL "
            "AND s.expires_at>clock_timestamp() AND s.credential_revision=c.credential_revision"
        ),
        {"session": session.session_id, "account": session.account.account_id},
    )
    if valid is None:
        # 会话已撤销/过期/账号停用或凭据代次不符。
        raise AuthError(401, "unauthenticated", "登录已失效，请重新登录。")
    if admin and valid != "admin":
        raise AuthError(403, "forbidden", "此操作仅限管理员。")


async def database_time(connection: AsyncConnection) -> datetime:
    now = await connection.scalar(text("SELECT clock_timestamp()"))
    if not isinstance(now, datetime):
        # 库时钟须返回时间值，否则无法落时间戳。
        raise RuntimeError("Database clock unavailable")
    return now


async def append_account_event(
    connection: AsyncConnection,
    store: EventStore,
    *,
    actor: Ref,
    account: UUID,
    event_type: str,
    payload: EventPayload,
    request_id: str,
    receipt_id: UUID,
    revision: int | None = None,
    schema_version: int = 1,
) -> UUID:
    seq = await connection.scalar(
        text(
            "SELECT last_seq FROM runtime.scope_event_heads "
            "WHERE scope_kind='account' AND scope_id=:id"
        ),
        {"id": account},
    )
    identity = uuid4()
    events = await store.append(
        connection,
        ProducerAccess("product", actor, frozenset({("account", account)})),
        [
            EventDraft(
                identity,
                event_type,
                schema_version,
                "account",
                account,
                Ref(owner="product", type="account", id=str(account), revision=revision),
                payload.model_dump(mode="json"),
                request_id,
            )
        ],
        commit_id=uuid4(),
        correlation_id=receipt_id,
        expected_seq={("account", account): seq or 0},
    )
    await apply_account_events(connection, events)
    return identity
