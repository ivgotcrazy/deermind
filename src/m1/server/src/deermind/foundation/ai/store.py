"""AI事实与投影的共同保存；所有者持工作锁，模型和文件I/O均在事务外。"""

import json
from datetime import datetime
from uuid import UUID, uuid4

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    INLINE_LIMIT,
    EventDraft,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.executions import Execution
from deermind.abstractions.hashing import digest
from deermind.foundation.ai.facts import REGISTRATIONS, AIEvent
from deermind.foundation.ai.projections import KEYS, apply_ai_events
from deermind.foundation.ai.records import ConfigurationFact
from deermind.foundation.system.events.store import EventStore
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def now(connection: AsyncConnection) -> datetime:
    value = await connection.scalar(text("SELECT clock_timestamp()"))
    if not isinstance(value, datetime):
        raise RuntimeError("Database did not return a timestamp")
    return value


async def load[Fact: FactModel](
    connection: AsyncConnection, table: str, model: type[Fact], keys: dict[str, object]
) -> Fact | None:
    """仅查询程序登记的表及主键；不允许模型提供表名、筛选或SQL片段。"""
    if table not in KEYS or set(keys) != set(KEYS[table]):
        raise ValueError("Unregistered AI projection read")
    where = " AND ".join(f"{key}=:{key}" for key in keys)
    row = (
        (await connection.execute(text(f"SELECT * FROM {table} WHERE {where}"), keys))
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    values = {key: value for key, value in row.items() if key != "source_event_id"}
    return model.model_validate_json(json.dumps(values, default=str))


async def record(
    connection: AsyncConnection,
    execution: Execution,
    event_type: str,
    outcome: str,
    facts: list[tuple[str, FactModel]],
    *,
    reason: str | None = None,
) -> None:
    """先追加完整事实，再调用AI自己的转换器；任何失败由外层整体回滚。"""
    subject = Ref(owner="ai", type="execution", id=str(execution.execution_id))
    records = [
        FactRecord(
            record_id=f"record-{index}",
            record_type=name,
            schema_version=1,
            content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
        )
        for index, (name, value) in enumerate(facts)
    ]
    # 正文大的材料/候选在事务外固定为附件；这里不可在持锁时写文件。
    if any(
        len(canonical_json(item.content.model_dump()).encode()) > INLINE_LIMIT for item in records
    ):
        raise ValueError("AI record must externalize its large content before committing")
    payload = AIEvent.model_validate(
        {
            "records": records,
            "subject_ref": subject,
            "outcome": outcome,
            "reason_code": reason,
        }
    )
    sequence = await connection.scalar(
        text(
            "SELECT last_seq FROM runtime.scope_event_heads "
            "WHERE scope_kind='execution' AND scope_id=:id"
        ),
        {"id": execution.execution_id},
    )
    events = await EventStore(REGISTRATIONS).append(
        connection,
        ProducerAccess("ai", subject, frozenset({("execution", execution.execution_id)})),
        [
            EventDraft(
                uuid4(),
                event_type,
                1,
                "execution",
                execution.execution_id,
                subject,
                payload.model_dump(mode="json"),
                execution.acceptance_key,
                source_execution_ref=execution.execution_id,
            )
        ],
        commit_id=uuid4(),
        correlation_id=execution.execution_id,
        expected_seq={("execution", execution.execution_id): sequence or 0},
    )
    await apply_ai_events(connection, events)


async def pin(
    connection: AsyncConnection, execution: Execution, config: ExecutionConfig
) -> ConfigurationFact:
    """与受理共用短事务；重复受理复用旧配置，配置变化只作用于新工作。"""
    if execution.kind != "ai_operation" or execution.ai_config_ref != execution.execution_id:
        raise ValueError("AI configuration identity must equal its execution identity")
    saved = await load(
        connection,
        "ai.execution_configs",
        ConfigurationFact,
        {"execution_id": execution.execution_id},
    )
    if saved is not None:
        return saved
    body = config.model_dump(mode="json")
    saved = ConfigurationFact(
        execution_id=execution.execution_id,
        config_revision=config.revision,
        config_hash=digest(body),
        config=body,
        created_at=await now(connection),
    )
    await record(
        connection,
        execution,
        "AIConfigurationPinned",
        "recorded",
        [("ai.execution_configs", saved)],
    )
    await connection.execute(
        text(
            "INSERT INTO ai.execution_usage (execution_id,updated_at) "
            "VALUES (:id,clock_timestamp())"
        ),
        {"id": execution.execution_id},
    )
    return saved


async def configuration(connection: AsyncConnection, execution_id: UUID) -> ExecutionConfig:
    saved = await load(
        connection, "ai.execution_configs", ConfigurationFact, {"execution_id": execution_id}
    )
    if saved is None:
        raise ValueError("configuration_unavailable")
    return ExecutionConfig.model_validate_json(canonical_json(saved.config))
