"""维护四类活动配置。事实正文先准备，指针、事实与收据共同提交。"""

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from deermind.abstractions.command_receipts import CommandReceipt, ReceiptCommands
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import (
    EventDraft,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.public.errors import RequestError
from deermind.foundation.system.public.receipts import ReceiptQuery, ReceiptView
from deermind.spaces.interaction import config_facts as facts
from deermind.spaces.interaction.blueprints import validate_bindings, validate_blueprint
from deermind.spaces.interaction.public import (
    MANAGE_ACTIVITY,
    ActivityType,
    BindingDefinition,
    BlueprintDefinition,
    BoundRule,
    BoundStrategy,
    ConfigCommand,
    ConfigKind,
    ConfigReceipt,
    ConfigResult,
    ConfigView,
    LocalBinding,
    ResolvedActivityConfig,
    RuleDefinition,
    SaveBinding,
    SaveBlueprint,
    SaveRule,
    StrategyDefinition,
)
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

ACTIVITY_TYPES: tuple[ActivityType, ...] = (
    "explanation",
    "question_answer",
    "detection",
    "free_chat",
)
OWNERS = {
    "blueprint": facts.BlueprintRevision,
    "binding": facts.BindingRevision,
    "rule": facts.RuleRevision,
    "strategy": facts.StrategyRevision,
}


def scope_id(activity: ActivityType) -> UUID:
    return uuid5(NAMESPACE_URL, "deermind:activity-config:" + activity)


def _record(
    kind: ConfigKind,
    reference: Ref,
    definition: BlueprintDefinition | BindingDefinition | RuleDefinition | StrategyDefinition,
    actor: Ref,
    now: datetime,
) -> FactRecord:
    data = {
        f"{kind}_id": reference.id,
        "revision": reference.revision,
        "activity_type": definition.activity_type,
        "definition": definition.model_dump(mode="json"),
        "actor_ref": actor.model_dump(mode="json"),
        "created_at": now.isoformat(),
    }
    value = OWNERS[kind].model_validate_json(canonical_json(data))
    return FactRecord(
        record_id=reference.id,
        record_type=facts.RECORD_TYPES[kind],
        schema_version=1,
        content=InlineContent(storage="inline", value=value.model_dump(mode="json")),
    )


def _next(kind: str, previous: Ref | None) -> Ref:
    if previous is None:
        return Ref(owner="interaction", type=kind, id=str(uuid4()), revision=1)
    assert previous.revision is not None
    return previous.model_copy(update={"revision": previous.revision + 1})


class ActivityConfigs:
    def __init__(
        self,
        engine: AsyncEngine,
        events: EventStore,
        reader: EventReader,
        attachments: FactAttachments,
        receipts: ReceiptCommands[AsyncConnection],
    ) -> None:
        self.engine = engine
        self.events = events
        self.reader = reader
        self.attachments = attachments
        self.receipts = receipts

    async def _fact(self, activity: ActivityType, event: UUID, record_id: str | None) -> JsonValue:
        result = await self.reader.read_facts(
            "activity_config",
            scope_id(activity),
            event,
            expected_event_type=facts.EVENT,
            refs=[EventPartRef(event_id=event, record_id=record_id, path="")],
        )
        items = result["items"]
        assert isinstance(items, list) and isinstance(items[0], dict)
        return items[0]["content"]

    async def _definition(self, activity: ActivityType, kind: ConfigKind, ref: Ref) -> JsonValue:
        table = facts.RECORD_TYPES[kind]
        async with self.engine.connect() as db:
            event = await db.scalar(
                text(
                    f"SELECT source_event_id FROM {table} WHERE activity_type=:type "
                    f"AND {kind}_id=:id AND revision=:revision"
                ),
                {"type": activity, "id": UUID(ref.id), "revision": ref.revision},
            )
        if event is None:
            raise RuntimeError("Configuration package has a missing immutable reference")
        value = await self._fact(activity, event, ref.id)
        assert isinstance(value, dict)
        return value["definition"]

    async def _load(
        self, activity: ActivityType, config_id: UUID | None
    ) -> tuple[ConfigView, facts.ActivityConfigSaved]:
        async with self.engine.connect() as db:
            row = (
                await db.execute(
                    text(
                        "SELECT p.config_id,p.source_event_id FROM interaction.resolved_configs p "
                        "LEFT JOIN interaction.config_heads h USING(activity_type) "
                        "WHERE p.activity_type=:type "
                        "AND p.config_id=COALESCE(CAST(:id AS uuid),h.config_id)"
                    ),
                    {"type": activity, "id": config_id},
                )
            ).one_or_none()
        if row is None:
            raise RequestError(404, "not_found", "未保存此活动的配置。")
        body = await self._fact(activity, row.source_event_id, str(row.config_id))
        packet = facts.ResolvedConfig.model_validate_json(canonical_json(body))
        action = await self._fact(activity, row.source_event_id, None)
        assert isinstance(action, dict)
        change = facts.ActivityConfigSaved.model_validate_json(
            canonical_json({**action, "records": []})
        )
        definition = ResolvedActivityConfig(
            activity_type=activity,
            blueprint_ref=packet.blueprint_ref,
            binding_ref=packet.binding_ref,
            blueprint=BlueprintDefinition.model_validate_json(
                canonical_json(await self._definition(activity, "blueprint", packet.blueprint_ref))
            ),
            binding=BindingDefinition.model_validate_json(
                canonical_json(await self._definition(activity, "binding", packet.binding_ref))
            ),
            rules=[
                BoundRule(
                    ref=item.ref,
                    definition=RuleDefinition.model_validate_json(
                        canonical_json(await self._definition(activity, "rule", item.ref))
                    ),
                )
                for item in packet.rule_refs
            ],
            strategies=[
                BoundStrategy(
                    ref=item.ref,
                    definition=StrategyDefinition.model_validate_json(
                        canonical_json(await self._definition(activity, "strategy", item.ref))
                    ),
                )
                for item in packet.strategy_refs
            ],
        )
        return ConfigView(
            config_ref=change.config_ref,
            definition=definition,
            gaps=validate_bindings(definition),
            usage_refs=[],
        ), change

    async def detail(self, activity_type: ActivityType, config_id: UUID | None) -> ConfigView:
        view, _ = await self._load(activity_type, config_id)
        return view

    async def fixed_config(self, reference: Ref) -> ConfigView:
        if reference.owner != "interaction" or reference.type != "activity_config":
            raise RequestError(400, "invalid_reference", "请选择完整的活动配置。")
        try:
            identity = UUID(reference.id)
        except ValueError as error:
            raise RequestError(400, "invalid_reference", "活动配置编号无效。") from error
        async with self.engine.connect() as db:
            activity: ActivityType | None = await db.scalar(
                text("SELECT activity_type FROM interaction.resolved_configs WHERE config_id=:id"),
                {"id": identity},
            )
        if activity is None:
            raise RequestError(404, "not_found", "找不到指定配置修订。")
        result = await self.detail(activity, identity)
        if result.config_ref != reference:
            raise RequestError(409, "invalid_reference", "活动配置修订不一致。")
        return result

    def _prepare_config(
        self,
        activity: ActivityType,
        body: ConfigCommand,
        prior: ConfigView | None,
        actor: Ref,
        now: datetime,
    ) -> tuple[ResolvedActivityConfig, Ref, list[FactRecord]]:
        if body.definition.activity_type != activity:
            raise RequestError(400, "invalid_reference", "配置不属于当前活动类型。")
        if prior is None:
            if not isinstance(body, SaveBlueprint) or body.config_ref is not None:
                raise RequestError(409, "blueprint_required", "请先保存活动蓝图。")
            validate_blueprint(body.definition)
            first_blueprint, first_binding = _next("blueprint", None), _next("binding", None)
            binding = BindingDefinition(
                activity_type=activity,
                activity=LocalBinding(rule_ids=[], strategy_ids=[]),
                nodes={},
            )
            return (
                ResolvedActivityConfig(
                    activity_type=activity,
                    blueprint_ref=first_blueprint,
                    binding_ref=first_binding,
                    blueprint=body.definition,
                    binding=binding,
                    rules=[],
                    strategies=[],
                ),
                first_blueprint,
                [
                    _record("blueprint", first_blueprint, body.definition, actor, now),
                    _record("binding", first_binding, binding, actor, now),
                ],
            )

        config = prior.definition
        candidates = {
            "blueprint": [config.blueprint_ref],
            "binding": [config.binding_ref],
            "rule": [rule.ref for rule in config.rules],
            "strategy": [s.ref for s in config.strategies],
        }
        current = candidates[body.config_kind]
        if (body.config_ref is not None and body.config_ref not in current) or (
            body.config_ref is None and isinstance(body, SaveBinding | SaveBlueprint)
        ):
            raise RequestError(409, "invalid_reference", "配置对象或修订不属于当前配置包。")
        reference = _next(body.config_kind, body.config_ref)
        changes = [_record(body.config_kind, reference, body.definition, actor, now)]
        if isinstance(body, SaveBlueprint):
            validate_blueprint(body.definition)
            valid_ids = {node.node_id for node in body.definition.nodes}
            nodes = {key: value for key, value in config.binding.nodes.items() if key in valid_ids}
            config = config.model_copy(
                update={"blueprint": body.definition, "blueprint_ref": reference}
            )
            if nodes != config.binding.nodes:
                binding = config.binding.model_copy(update={"nodes": nodes})
                binding_ref = _next("binding", config.binding_ref)
                config = config.model_copy(update={"binding": binding, "binding_ref": binding_ref})
                changes.append(_record("binding", binding_ref, binding, actor, now))
        elif isinstance(body, SaveBinding):
            config = config.model_copy(
                update={"binding": body.definition, "binding_ref": reference}
            )
        elif isinstance(body, SaveRule):
            kept = [rule for rule in config.rules if rule.ref != body.config_ref]
            config = config.model_copy(
                update={"rules": [*kept, BoundRule(ref=reference, definition=body.definition)]}
            )
        else:
            kept_strategies = [s for s in config.strategies if s.ref != body.config_ref]
            config = config.model_copy(
                update={
                    "strategies": [
                        *kept_strategies,
                        BoundStrategy(ref=reference, definition=body.definition),
                    ]
                }
            )
        return config, reference, changes

    async def _replay(self, activity: ActivityType, receipt: CommandReceipt) -> ConfigReceipt:
        assert receipt.result_ref is not None
        view, change = await self._load(activity, UUID(receipt.result_ref.id))
        return ConfigReceipt(
            request_ref=receipt.request_ref,
            result=ConfigResult(
                config_ref=view.config_ref,
                definition_ref=change.definition_ref,
                affected_refs=[view.definition.binding_ref],
                gaps=view.gaps,
            ),
        )

    async def receipt(
        self, principal: UUID, _session: UUID, query: ReceiptQuery
    ) -> ReceiptView[ConfigResult]:
        activity: ActivityType | None = next(
            (item for item in ACTIVITY_TYPES if scope_id(item) == query.resource_id), None
        )
        if activity is None:
            return ReceiptView[ConfigResult](receipt_state="not_found")
        async with self.engine.connect() as db:
            saved = await self.receipts.find_completed_request(
                db, principal, MANAGE_ACTIVITY, query.resource_id, query.request_id
            )
        if saved is None:
            return ReceiptView[ConfigResult](receipt_state="not_found")
        result = await self._replay(activity, saved)
        return ReceiptView[ConfigResult](
            receipt_state="completed", receipt_ref=result.request_ref, result=result.result
        )

    async def save(
        self, principal: UUID, activity: ActivityType, body: ConfigCommand
    ) -> ConfigReceipt:
        normalized = body.model_dump(mode="json")
        identity = scope_id(activity)
        async with self.engine.connect() as db:
            saved = await self.receipts.find_completed_request(
                db, principal, MANAGE_ACTIVITY, identity, body.request_id, normalized
            )
        if saved is not None:
            return await self._replay(activity, saved)
        try:
            prior = await self.detail(activity, None)
        except RequestError as error:
            if error.status != 404:
                raise
            prior = None
        previous = prior.config_ref if prior is not None else None
        if body.expected_revision != (previous.revision if previous else None):
            raise RequestError(409, "revision_conflict", "活动配置已变化，请重新读取。")
        now = datetime.now(UTC)
        actor = Ref(owner="product", type="account", id=str(principal))
        config, definition_ref, records = self._prepare_config(activity, body, prior, actor, now)
        gaps = validate_bindings(config)
        request = uuid4()
        reference = Ref(
            owner="interaction",
            type="activity_config",
            id=str(uuid4()),
            revision=(body.expected_revision or 0) + 1,
        )
        packet = facts.ResolvedConfig(
            config_id=UUID(reference.id),
            activity_type=activity,
            blueprint_ref=config.blueprint_ref,
            binding_ref=config.binding_ref,
            created_at=now,
            rule_refs=[
                facts.BoundRef(ref=r.ref, enabled=r.definition.enabled) for r in config.rules
            ],
            strategy_refs=[
                facts.BoundRef(ref=r.ref, enabled=r.definition.enabled) for r in config.strategies
            ],
        )
        records.append(
            FactRecord(
                record_id=reference.id,
                record_type=facts.RESOLVED,
                schema_version=1,
                content=InlineContent(storage="inline", value=packet.model_dump(mode="json")),
            )
        )
        change = facts.ActivityConfigSaved(
            activity_type=activity,
            config_kind=body.config_kind,
            definition_ref=definition_ref,
            config_ref=reference,
            previous_config_ref=previous,
            request_ref=request,
            records=records,
        )
        scope = ("activity_config", identity)
        access = ProducerAccess("interaction", actor, frozenset({scope}))
        draft = EventDraft(
            uuid4(),
            facts.EVENT,
            1,
            *scope,
            reference,
            change.model_dump(mode="json"),
            body.request_id,
        )
        prepared = await self.attachments.prepare(self.events, access, (draft,))
        async with self.engine.begin() as db:
            receipt = await self.receipts.claim_request(
                db,
                principal_id=str(principal),
                action=MANAGE_ACTIVITY,
                scope_id=str(identity),
                request_id=body.request_id,
                normalized_input=normalized,
                reserved_ref=request,
            )
            if receipt.result_ref is None:
                sequence = await lock_scope_sequence(db, *scope)
                head = await db.scalar(
                    text(
                        "SELECT config_id FROM interaction.config_heads WHERE activity_type=:type"
                    ),
                    {"type": activity},
                )
                if head != (UUID(previous.id) if previous else None):
                    raise RequestError(409, "revision_conflict", "活动配置已变化，请重新读取。")
                (stored,) = await self.events.append(
                    db,
                    access,
                    prepared,
                    commit_id=uuid4(),
                    correlation_id=request,
                    expected_seq={scope: sequence},
                )
                await facts.project(db, stored)
                await self.receipts.complete_request(db, receipt, reference)
                return ConfigReceipt(
                    request_ref=request,
                    result=ConfigResult(
                        config_ref=reference,
                        definition_ref=definition_ref,
                        affected_refs=[config.binding_ref],
                        gaps=gaps,
                    ),
                )
        return await self._replay(activity, receipt)
