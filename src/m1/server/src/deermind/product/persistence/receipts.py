"""普通写命令的事务内防重；唯一键竞争由PostgreSQL协调。"""

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.product.public.errors import RequestConflict as RequestConflict
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Receipt:
    request_ref: UUID
    result_ref: Ref | None


async def claim_request(
    connection: AsyncConnection,
    *,
    principal_id: str,
    action: str,
    scope_id: str,
    request_id: str,
    normalized_input: dict[str, JsonValue],
) -> Receipt:
    """先取得收据身份；竞争者等待原事务，然后读取同一结果。

    这里的accepted不会单独提交。事件或投影失败时收据也回滚，重试仍可完整执行。
    本函数只能接收已验证、已剔除凭据的输入。
    """
    if not connection.in_transaction() or not all((principal_id, action, scope_id, request_id)):
        raise ValueError("Receipt requires a transaction and nonempty identity")
    body = canonical_json(normalized_input)
    parameters: dict[str, object] = {
        "ref": uuid4(),
        "principal": principal_id,
        "action": action,
        "scope": scope_id,
        "request": request_id,
        "digest": sha256(body.encode("utf-8")).hexdigest(),
        "body": body,
    }
    inserted = await connection.scalar(
        text(
            "INSERT INTO product.command_receipt "
            "(request_ref, principal_id, action, scope_id, request_id, input_digest, "
            "normalized_input, "
            "state, result_ref, error, created_at, updated_at) "
            "VALUES (:ref, :principal, :action, :scope, :request, :digest, CAST(:body AS jsonb), "
            "'accepted', NULL, NULL, clock_timestamp(), clock_timestamp()) "
            "ON CONFLICT (principal_id, action, scope_id, request_id) DO NOTHING "
            "RETURNING request_ref"
        ),
        parameters,
    )
    if isinstance(inserted, UUID):
        return Receipt(inserted, None)
    row = (
        (
            await connection.execute(
                text(
                    "SELECT request_ref, input_digest, normalized_input, state, result_ref "
                    "FROM product.command_receipt WHERE principal_id=:principal AND action=:action "
                    "AND scope_id=:scope AND request_id=:request FOR UPDATE"
                ),
                parameters,
            )
        )
        .mappings()
        .one()
    )
    if row["input_digest"] != parameters["digest"] or row["normalized_input"] != normalized_input:
        raise RequestConflict("Request identity was already used with different input")
    if row["state"] != "completed" or row["result_ref"] is None:
        raise RequestConflict("Receipt has no completed synchronous result")
    return Receipt(row["request_ref"], Ref.model_validate(row["result_ref"]))


async def complete_request(connection: AsyncConnection, receipt: Receipt, result: Ref) -> Receipt:
    """原事务内一次落定，调用方仅在事务提交后返回。"""
    completed = await connection.scalar(
        text(
            "UPDATE product.command_receipt SET state='completed', "
            "result_ref=CAST(:result AS jsonb), updated_at=clock_timestamp() "
            "WHERE request_ref=:ref AND state='accepted' RETURNING request_ref"
        ),
        {"ref": receipt.request_ref, "result": result.model_dump_json(exclude_none=True)},
    )
    if completed != receipt.request_ref:
        raise RequestConflict("Receipt is not awaiting completion")
    return Receipt(receipt.request_ref, result)
