"""账号业务的确定性生成器；保存、订阅处理和重建共用，不产生新业务动作。"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import StoredEvent
from deermind.foundation.system.projections.receipts import application
from deermind.product.accounts.facts import AccountFact, account_values
from deermind.product.accounts.usage_events import decode
from deermind.product.accounts.usage_facts import USAGE_RECORDS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

PROJECTOR_ID = "product.account_views.v2"
EVENT_TYPES = frozenset({"TrialAccountSaved", "UsageConfirmationRecorded"})


@dataclass(frozen=True)
class AccountTable:
    name: str
    key: str
    columns: tuple[str, ...]
    update_columns: tuple[str, ...] = ()


# 顺序由账号业务的依赖决定，不由事件底座推测。
TABLES = (
    AccountTable(
        "product.accounts",
        "account_id",
        (*AccountFact.model_fields, "source_event_id"),
        ("login_identifier", "display_name", "status", "revision", "source_event_id"),
    ),
    *(
        AccountTable(
            name,
            next(iter(model.model_fields)),
            (*model.model_fields, "source_event_id"),
            tuple(c for c in (*model.model_fields, "source_event_id") if c != "student_id")
            if name == "product.usage_conditions"
            else (),
        )
        for (name, _), model in USAGE_RECORDS.items()
    ),
)
JSON_FIELDS = frozenset(
    {
        "verified_identity_ref",
        "verification_ref",
        "actor_ref",
        "notice_ref",
        "source_ref",
        "confirmation_refs",
        "reasons",
    }
)


def stage_tables(identity: UUID) -> dict[str, str]:
    """副本只由程序生成，命令和事件不能提供SQL目标。"""
    return {t.name: f"product.rb_{identity.hex}_{t.name.split('.')[1]}" for t in TABLES}


def target_tables(targets: Mapping[str, str] | None) -> Mapping[str, str]:
    if targets is None:
        # 常规投影直写正式表。
        return {t.name: t.name for t in TABLES}
    if set(targets) != {t.name for t in TABLES} or any(
        not re.fullmatch(r"product\.rb_[0-9a-f]{32}_" + t.name.split(".")[1], targets[t.name])
        for t in TABLES
    ):
        # 重建副本表名须按约定前缀生成，禁止调用方任意指定 SQL 目标。
        raise ValueError("Account projection targets must be a registered maintenance copy")
    prefixes = {name.split("_")[1] for name in targets.values()}
    if len(prefixes) != 1:
        # 同一轮重建的副本必须共用同一身份前缀。
        raise ValueError("Account projection targets belong to different rebuilds")
    return targets


def rows_for(event: StoredEvent) -> dict[str, list[dict[str, object]]]:
    """一个事件可含多行、多表；当前值取已保存快照，不重新计算使用资格。"""
    rows: dict[str, list[dict[str, object]]] = {t.name: [] for t in TABLES}
    if event.draft.event_type not in EVENT_TYPES:
        # 非账号相关事件不参与账号视图投影。
        return rows
    if event.draft.scope_kind != "account":
        raise ValueError("Account projection requires account facts")
    if event.draft.event_type == "TrialAccountSaved":
        # 账号保存事件落账号主表当前快照。
        rows["product.accounts"].append(account_values(event))
    for record in event.payload.records:
        if (record.record_type, record.schema_version) in USAGE_RECORDS:
            fact = decode(record)
            values: dict[str, object] = fact.model_dump()
            serialized = fact.model_dump(mode="json")
            for key in JSON_FIELDS & values.keys():
                # JSON 列按规范化序列化值入库，避免 Python 对象直接落库。
                values[key] = serialized[key]
            rows[record.record_type].append({**values, "source_event_id": event.draft.event_id})
    return rows


async def apply_account_events(
    connection: AsyncConnection,
    events: Sequence[StoredEvent],
    *,
    generation: int = 1,
    targets: Mapping[str, str] | None = None,
) -> None:
    """调用者先保护业务对象；投影和完成收据必须与外层事务共同提交或回滚。"""
    destinations = target_tables(targets)
    if (generation == 1) != (targets is None):
        # 常规代际写正式表；重建代际只能写副本，二者不可混用。
        raise ValueError("Maintenance generation cannot write live account projections")
    for event in events:
        if event.draft.event_type not in EVENT_TYPES:
            continue
        async with application(connection, PROJECTOR_ID, generation, event.draft.event_id) as apply:
            if not apply:
                # 该事件收据已应用过，幂等重放跳过。
                continue
            rows = rows_for(event)
            for table in TABLES:
                for values in rows[table.name]:
                    parameters = dict(values)
                    for key in JSON_FIELDS & parameters.keys():
                        parameters[key] = canonical_json(parameters[key])
                    expressions = ",".join(
                        f"CAST(:{c} AS jsonb)" if c in JSON_FIELDS else f":{c}"
                        for c in table.columns
                    )
                    conflict = ""
                    if table.update_columns:
                        # 有更新列的表按主键冲突覆盖当前快照。
                        conflict = f" ON CONFLICT ({table.key}) DO UPDATE SET " + ",".join(
                            f"{c}=EXCLUDED.{c}" for c in table.update_columns
                        )
                    await connection.execute(
                        text(
                            f"INSERT INTO {destinations[table.name]} ({','.join(table.columns)}) "
                            f"VALUES ({expressions}){conflict}"
                        ),
                        parameters,
                    )
