"""已授权的初始账号事实保存；不提供开户、凭据或HTTP入口。"""

from datetime import datetime
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.foundation.system.events.store import EventStore
from deermind.product.accounts.facts import AccountFact, AccountSaved
from deermind.product.accounts.projections import apply_account_events
from deermind.product.persistence.receipts import Receipt, claim_request, complete_request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def save_initial_account(
    engine: AsyncEngine,
    store: EventStore,
    access: ProducerAccess,
    *,
    request_id: str,
    account_id: UUID,
    login_identifier: str,
    display_name: str,
) -> Receipt:
    """事件、生产者投影、投影收据、请求收据共同提交。

    仅供受信装配及事务验证调用。后续账号入口必须先完成管理员/引导授权，
    不能把本函数当作免认证的账号创建API。新账号身份由调用方固定并在重试沿用。
    """
    if access.producer != "product" or ("account", account_id) not in access.scopes:
        raise PermissionError("Account scope is not authorized")
    owner = Ref(owner="product", type="account", id=str(account_id), revision=1)
    async with engine.begin() as connection:
        receipt = await claim_request(
            connection,
            principal_id=canonical_actor(access.actor_ref),
            action="bootstrap_admin",
            scope_id=str(account_id),
            request_id=request_id,
            normalized_input={
                "account_id": str(account_id),
                "login_identifier": login_identifier,
                "display_name": display_name,
            },
        )
        if receipt.result_ref is not None:
            return receipt
        created_at = await connection.scalar(text("SELECT clock_timestamp()"))
        if not isinstance(created_at, datetime):
            raise RuntimeError("Database did not return a timestamp")
        fact = AccountFact(
            account_id=account_id,
            login_identifier=login_identifier,
            display_name=display_name,
            role="admin",
            status="active",
            revision=1,
            created_at=created_at,
        )
        payload = AccountSaved(
            account_id=account_id,
            action="bootstrap_admin",
            account_revision=1,
            relation_refs=[],
            records=[
                FactRecord(
                    record_id="account",
                    record_type="product.accounts",
                    schema_version=1,
                    content=InlineContent(storage="inline", value=fact.model_dump(mode="json")),
                )
            ],
        )
        events = await store.append(
            connection,
            access,
            [
                EventDraft(
                    event_id=uuid4(),
                    event_type="TrialAccountSaved",
                    schema_version=1,
                    scope_kind="account",
                    scope_id=account_id,
                    owner_ref=owner,
                    payload=payload.model_dump(mode="json"),
                    source_request_id=request_id,
                )
            ],
            commit_id=uuid4(),
            correlation_id=receipt.request_ref,
            expected_seq={("account", account_id): 0},
        )
        await apply_account_events(connection, events)
        result = await complete_request(connection, receipt, owner)
    return result


def canonical_actor(actor: Ref) -> str:
    """调用者身份不含展示字段、修订或路径，避免同一人产生多组防重键。"""
    return canonical_json([actor.owner, actor.type, actor.id])
