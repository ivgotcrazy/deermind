"""账号业务的确定性生成器；保存、订阅处理和重建共用，不产生新业务动作。"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from deermind.foundation.system.events.contracts import StoredEvent
from deermind.foundation.system.events.store import canonical_json
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
        return {t.name: t.name for t in TABLES}
    if set(targets) != {t.name for t in TABLES} or any(
        not re.fullmatch(r"product\.rb_[0-9a-f]{32}_" + t.name.split(".")[1], targets[t.name])
        for t in TABLES
    ):
        raise ValueError("Account projection targets must be a registered maintenance copy")
    prefixes = {name.split("_")[1] for name in targets.values()}
    if len(prefixes) != 1:
        raise ValueError("Account projection targets belong to different rebuilds")
    return targets


def rows_for(event: StoredEvent) -> dict[str, list[dict[str, object]]]:
    """一个事件可含多行、多表；当前值取已保存快照，不重新计算使用资格。"""
    rows: dict[str, list[dict[str, object]]] = {t.name: [] for t in TABLES}
    if event.draft.event_type not in EVENT_TYPES:
        return rows
    if event.draft.scope_kind != "account":
        raise ValueError("Account projection requires account facts")
    if event.draft.event_type == "TrialAccountSaved":
        rows["product.accounts"].append(account_values(event))
    for record in event.payload.records:
        if (record.record_type, record.schema_version) in USAGE_RECORDS:
            fact = decode(record)
            values: dict[str, object] = fact.model_dump()
            serialized = fact.model_dump(mode="json")
            for key in JSON_FIELDS & values.keys():
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
        raise ValueError("Maintenance generation cannot write live account projections")
    for event in events:
        if event.draft.event_type not in EVENT_TYPES:
            continue
        async with application(connection, PROJECTOR_ID, generation, event.draft.event_id) as apply:
            if not apply:
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
