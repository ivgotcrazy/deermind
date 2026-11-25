"""活动配置修订事实和 Interaction 所有的配置投影。"""

from datetime import datetime
from uuid import UUID

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    InlineContent,
    Ref,
    StoredEvent,
)
from deermind.foundation.system.projections.receipts import application
from deermind.spaces.interaction.public import (
    ActivityType,
    BindingDefinition,
    BlueprintDefinition,
    ConfigKind,
    RuleDefinition,
    StrategyDefinition,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

EVENT = "ActivityConfigSaved"
BLUEPRINT = "interaction.blueprint_revisions"
RULE = "interaction.rule_revisions"
STRATEGY = "interaction.strategy_revisions"
BINDING = "interaction.binding_revisions"
RESOLVED = "interaction.resolved_configs"


class ConfigRevision(FactModel):
    revision: int
    activity_type: ActivityType
    actor_ref: Ref
    created_at: datetime


class BlueprintRevision(ConfigRevision):
    blueprint_id: UUID
    definition: BlueprintDefinition


class RuleRevision(ConfigRevision):
    rule_id: UUID
    definition: RuleDefinition


class StrategyRevision(ConfigRevision):
    strategy_id: UUID
    definition: StrategyDefinition


class BindingRevision(ConfigRevision):
    binding_id: UUID
    definition: BindingDefinition


class BoundRef(FactModel):
    ref: Ref
    enabled: bool


class ResolvedConfig(FactModel):
    config_id: UUID
    activity_type: ActivityType
    blueprint_ref: Ref
    binding_ref: Ref
    rule_refs: list[BoundRef]
    strategy_refs: list[BoundRef]
    created_at: datetime


class ActivityConfigSaved(EventPayload):
    activity_type: ActivityType
    config_kind: ConfigKind
    definition_ref: Ref
    config_ref: Ref
    previous_config_ref: Ref | None
    request_ref: UUID


RECORD_TYPES: dict[ConfigKind, str] = {
    "blueprint": BLUEPRINT,
    "rule": RULE,
    "strategy": STRATEGY,
    "binding": BINDING,
}


def validate(draft: EventDraft, payload: EventPayload) -> None:
    # 事件类型与所有者引用须与配置结果引用一致。
    if not isinstance(payload, ActivityConfigSaved) or draft.owner_ref != payload.config_ref:
        raise ValueError("Activity configuration fact identity differs")
    records = {item.record_type: item for item in payload.records}
    record_type = RECORD_TYPES[payload.config_kind]
    expected = {record_type, RESOLVED}
    # 蓝图新建或附带绑定时，记录集合还须包含绑定修订。
    if payload.config_kind == "blueprint" and (
        payload.previous_config_ref is None or BINDING in records
    ):
        expected.add(BINDING)
    # 实际记录集合须与预期的修订对象加解析包一一对应。
    if set(records) != expected or len(payload.records) != len(expected):
        raise ValueError("Expected one written object revision and one resolved package")
    resolved = records[RESOLVED].content
    changed = records[record_type]
    assert isinstance(resolved, InlineContent) and isinstance(changed.content, InlineContent)
    if BINDING in expected:
        binding = records[BINDING].content
        assert isinstance(binding, InlineContent)
        linked = Ref.model_validate(resolved.value["binding_ref"])
        # 绑定修订的标识、版本与活动类型须与解析包内引用一致。
        if (
            binding.value["binding_id"] != linked.id
            or binding.value["revision"] != linked.revision
            or binding.value["activity_type"] != payload.activity_type
        ):
            raise ValueError("Binding version cannot differ from the resolved package")
    # 解析包与修订记录的标识、活动类型、版本及对象编号须与固定引用逐项吻合。
    if (
        resolved.value["config_id"] != payload.config_ref.id
        or resolved.value["activity_type"] != payload.activity_type
        or changed.content.value["activity_type"] != payload.activity_type
        or changed.content.value["revision"] != payload.definition_ref.revision
        or changed.content.value[f"{payload.config_kind}_id"] != payload.definition_ref.id
    ):
        raise ValueError("Configuration snapshot does not match its fixed references")


REGISTRATION = EventRegistration(
    EVENT,
    1,
    "interaction",
    "activity_config",
    ActivityConfigSaved,
    validate,
    {
        (BLUEPRINT, 1): BlueprintRevision,
        (RULE, 1): RuleRevision,
        (STRATEGY, 1): StrategyRevision,
        (BINDING, 1): BindingRevision,
        (RESOLVED, 1): ResolvedConfig,
    },
)


async def project(connection: AsyncConnection, saved: StoredEvent) -> None:
    change = saved.payload
    assert isinstance(change, ActivityConfigSaved)
    async with application(
        connection, "interaction.activity_configs", 1, saved.draft.event_id
    ) as needed:
        # 事件已投影过，重复应用直接返回。
        if not needed:
            return
        for item in change.records:
            content = item.content
            assert isinstance(content, InlineContent)
            table = item.record_type
            # 表类型须属于四类修订或解析包。
            if table not in {*RECORD_TYPES.values(), RESOLVED}:
                raise ValueError("Unexpected activity configuration record")
            await connection.execute(
                text(
                    f"INSERT INTO {table} SELECT * FROM "
                    f"jsonb_populate_record(NULL::{table},CAST(:body AS jsonb))"
                ),
                {
                    "body": canonical_json(
                        {**content.value, "source_event_id": str(saved.draft.event_id)}
                    )
                },
            )
        await connection.execute(
            text(
                "INSERT INTO interaction.config_heads(activity_type,config_id,revision) "
                "VALUES (:type,:id,:revision) ON CONFLICT(activity_type) "
                "DO UPDATE SET config_id=EXCLUDED.config_id,revision=EXCLUDED.revision"
            ),
            {
                "type": change.activity_type,
                "id": UUID(change.config_ref.id),
                "revision": change.config_ref.revision,
            },
        )
