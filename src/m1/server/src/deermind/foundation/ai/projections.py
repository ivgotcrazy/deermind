"""AI 所有者的确定性投影器；事件底座不选择表、不推算用量、不执行模型。

分层定位：foundation（AI 底座）
对外契约：apply_ai_events 把 AI 事件记录写入对应投影表；表名与主键由本所有者登记。
边界约束：只做事件到投影的确定性落库，不推算用量、不触发模型或后续工作。
"""

from collections.abc import Sequence

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import StoredEvent
from deermind.foundation.ai.facts import MATRIX, MODELS, decode
from deermind.foundation.system.projections.receipts import application
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# 各投影表的主键字段，读取与冲突定位均以此为准。
KEYS = {
    "ai.execution_configs": ("execution_id",),
    "ai.ai_calls": ("call_id",),
    "ai.ai_call_attempts": ("call_id", "attempt_id"),
    "ai.model_requests": ("call_id", "attempt_id", "request_ordinal", "transport_attempt"),
    "ai.tool_actions": ("tool_action_key", "attempt_id"),
    "ai.ai_candidates": ("candidate_id",),
}
# 重放或冲突时允许被新事件覆盖的可变字段；其余字段为固定输入，不允许借新事件改写。
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
# 以 jsonb 序列化的字段名集合，写入时按 JSON 编码。
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
    # 逐条事件重放；非 AI 所有者登记的事件类型跳过。
    for event in events:
        if event.draft.event_type not in MATRIX:
            continue
        async with application(connection, "ai.call_views.v1", 1, event.draft.event_id) as apply:
            # 同一事件已被应用过（幂等重放），跳过不重复落投影。
            if not apply:
                continue
            # 事件内逐条事实写入对应投影表。
            for record in event.payload.records:
                fact = decode(record)
                name = record.record_type
                keys = KEYS[name]
                columns = (*MODELS[name].model_fields, "source_event_id")
                values = {**fact.model_dump(), "source_event_id": event.draft.event_id}
                serialized = fact.model_dump(mode="json")
                # jsonb 字段按规范化 JSON 编码；空值保持 None。
                for field in JSON_FIELDS & values.keys():
                    values[field] = (
                        canonical_json(serialized[field]) if values[field] is not None else None
                    )
                # 按字段类型生成占位表达式：jsonb 字段显式转型。
                expressions = ",".join(
                    f"CAST(:{field} AS jsonb)" if field in JSON_FIELDS else f":{field}"
                    for field in columns
                )
                updates = MUTABLE.get(name, ())
                conflict = ""
                # 存在可变字段才生成冲突更新；无可变字段的表只允许插入。
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
                # 未命中单行插入/更新，说明固定字段被新事件改写，判不可变冲突。
                if result.rowcount != 1:
                    raise ValueError("AI projection conflicts with immutable fields")
