"""AI所有者的确定性投影器；事件底座不选择表、不推算用量、不执行模型。"""

from collections.abc import Sequence

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import StoredEvent
from deermind.foundation.ai.facts import MATRIX, MODELS, decode
from deermind.foundation.system.projections.receipts import application
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

KEYS = {
    "ai.execution_configs": ("execution_id",),
    "ai.ai_calls": ("call_id",),
    "ai.ai_call_attempts": ("call_id", "attempt_id"),
    "ai.model_requests": ("call_id", "attempt_id", "request_ordinal", "transport_attempt"),
    "ai.tool_actions": ("tool_action_key", "attempt_id"),
    "ai.ai_candidates": ("candidate_id",),
}
MUTABLE = {
    "ai.ai_calls": ("state", "candidate_ref"),
    "ai.ai_call_attempts": ("finished_at", "outcome", "error", "valid_candidate"),
    "ai.model_requests": (
        "actual_input_tokens",
        "actual_output_tokens",
        "usage_state",
        "provider_request_id",
        "outcome",
        "finished_at",
        "response_ref",
    ),
    "ai.tool_actions": ("result_ref", "owner_receipt_ref", "outcome", "finished_at"),
}
JSON_FIELDS = frozenset(
    {
        "config",
        "schema_ref",
        "input_ref",
        "error",
        "request_ref",
        "response_ref",
        "parameters_ref",
        "result_ref",
        "owner_receipt_ref",
        "content",
        "material_refs",
        "tool_refs",
    }
)


async def apply_ai_events(connection: AsyncConnection, events: Sequence[StoredEvent]) -> None:
    """调用方持有工作锁和共同事务；重复事件返回，不生成通知或后续工作。"""
    for event in events:
        if event.draft.event_type not in MATRIX:
            continue
        async with application(connection, "ai.call_views.v1", 1, event.draft.event_id) as apply:
            if not apply:
                continue
            for record in event.payload.records:
                fact = decode(record)
                name = record.record_type
                keys = KEYS[name]
                columns = (*MODELS[name].model_fields, "source_event_id")
                values = {**fact.model_dump(), "source_event_id": event.draft.event_id}
                serialized = fact.model_dump(mode="json")
                for field in JSON_FIELDS & values.keys():
                    values[field] = (
                        canonical_json(serialized[field]) if values[field] is not None else None
                    )
                expressions = ",".join(
                    f"CAST(:{field} AS jsonb)" if field in JSON_FIELDS else f":{field}"
                    for field in columns
                )
                updates = MUTABLE.get(name, ())
                conflict = ""
                if updates:
                    conflict = f" ON CONFLICT ({','.join(keys)}) DO UPDATE SET " + ",".join(
                        f"{field}=EXCLUDED.{field}" for field in (*updates, "source_event_id")
                    )
                    # 固定输入不允许借新事件覆盖；冲突必须导致外层事务回滚。
                    fixed = set(columns) - set(updates) - {"source_event_id"}
                    conflict += " WHERE " + " AND ".join(
                        f"{name}.{field} IS NOT DISTINCT FROM EXCLUDED.{field}"
                        for field in sorted(fixed)
                    )
                result = await connection.execute(
                    text(
                        f"INSERT INTO {name} ({','.join(columns)}) VALUES ({expressions}){conflict}"
                    ),
                    values,
                )
                if result.rowcount != 1:
                    raise ValueError("AI projection conflicts with immutable fields")
