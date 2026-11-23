"""只由 Domain 按固定要求供题，库存判断与批次结果共用一次事务。"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4, uuid5

from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.event_reading import EventPartRef
from deermind.abstractions.events import (
    EventDraft,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.task_supply import (
    COMPLETED,
    REQUESTED,
    DomainTaskSupplyCompleted,
    SuppliedTask,
    TaskSupplyRequested,
)
from deermind.abstractions.waits import Match
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.spaces.domain import analysis_facts, supply_facts
from deermind.spaces.domain.instances import chapter_methods, require_definition
from deermind.spaces.domain.public import (
    InstanceRef,
    InstanceView,
    SolutionDefinition,
    SolutionRef,
    TaskDefinition,
    TaskInstance,
    TaskRef,
)
from deermind.spaces.domain.supply_generation import Basis, GenerateSupply
from deermind.spaces.domain.supply_selection import select_instances

SCOPE = "learning_space"


def _ref(kind: str, value: UUID, version: int | None = None) -> Ref:
    return Ref(owner="domain", type=kind, id=str(value), version=version)


def _record(kind: str, identity: UUID, body: FactModel) -> FactRecord:
    return FactRecord(
        record_id=str(identity),
        record_type=kind,
        schema_version=1,
        content=InlineContent(storage="inline", value=body.model_dump(mode="json")),
    )


def _artifact(
    requested: TaskSupplyRequested,
    identity: UUID,
    kind: Literal["input", "use_check"],
    payload: dict[str, JsonValue],
    now: datetime,
) -> analysis_facts.AnalysisArtifact:
    return analysis_facts.AnalysisArtifact(
        artifact_id=identity,
        domain_id=requested.domain_id,
        kind=kind,
        input_ref=requested.supply_input_ref,
        definition_refs=[requested.task_ref, *requested.allowed_method_refs],
        payload=payload,
        rule_ref=Ref(owner="domain", type="rule", id="existing_task_supply", version=1),
        model_call_ref=None,
        command_ref=requested.request_ref,
        created_at=now,
    )


class TaskSupply:
    def __init__(
        self, events: EventStore, reader: EventReader, generation: GenerateSupply | None = None
    ) -> None:
        self.events = events
        self.reader = reader
        self.generation = generation

    @staticmethod
    async def read_batch(
        db: AsyncConnection, scope: UUID, trigger: UUID
    ) -> supply_facts.SupplyBatch | None:
        """按原学习空间与触发身份补读保存结果。"""
        body = await db.scalar(
            text(
                "SELECT to_jsonb(b)-'source_event_id' FROM domain.supply_batch b "
                "WHERE scope_id=:scope AND trigger_event_id=:trigger"
            ),
            {"scope": scope, "trigger": trigger},
        )
        return supply_facts.SupplyBatch.model_validate_json(canonical_json(body)) if body else None

    @staticmethod
    async def find_batch_result(db: AsyncConnection, scope: UUID, trigger: UUID) -> Match | None:
        batch = await TaskSupply.read_batch(db, scope, trigger)
        if batch is None:
            return None
        return Match(
            event_id=batch.completed_event_id, result_ref=_ref("supply_batch", batch.batch_id)
        )

    @staticmethod
    async def read_supplied_question(
        db: AsyncConnection, scope: UUID, trigger: UUID
    ) -> tuple[TaskInstance, SuppliedTask, UUID] | None:
        batch = await TaskSupply.read_batch(db, scope, trigger)
        if batch is None or not batch.items:
            return None
        item = batch.items[0]
        body = await TaskSupply.read_fixed_question(db, item.task_instance_ref)
        return (body, item, batch.completed_event_id) if body else None

    @staticmethod
    async def read_fixed_question(db: AsyncConnection, fixed: Ref) -> TaskInstance | None:
        if fixed.owner != "domain" or fixed.type != "task_instance" or fixed.version is None:
            return None
        body = await db.scalar(
            text(
                "SELECT v.content FROM domain.object_identity i "
                "JOIN domain.object_version v USING(object_id) "
                "JOIN domain.object_version h "
                "ON (h.object_id,h.version)=(i.object_id,i.head_version) "
                "WHERE i.object_id=:id AND i.kind='task_instance' AND v.version=:version "
                "AND NOT v.is_deleted AND NOT h.is_deleted"
            ),
            {"id": UUID(fixed.id), "version": fixed.version},
        )
        return TaskInstance.model_validate_json(canonical_json(body)) if body else None

    async def receive(self, db: AsyncConnection, notice: EventNotice) -> Acceptance:
        """按已登记通知读取原需求。在重投时返回同一个供题批次。"""
        if (
            notice.scope_kind != SCOPE
            or notice.event_type != REQUESTED
            or notice.producer != "interaction"
        ):
            return Acceptance(disposition="ignored", arrangement_refs=[])
        trigger, scope = notice.event_id, notice.scope_id
        batch_id = uuid5(trigger, "task-supply-batch")
        batch = _ref("supply_batch", batch_id)
        answer = Acceptance(disposition="accepted", arrangement_refs=[batch])
        if await self._exists(db, trigger, scope):
            return answer
        data = await self.reader.read_facts(
            SCOPE,
            scope,
            trigger,
            refs=[EventPartRef(event_id=trigger, record_id=None, path="")],
            expected_event_type=REQUESTED,
        )
        items = data["items"]
        assert (
            isinstance(items, list)
            and isinstance(items[0], dict)
            and isinstance(items[0]["content"], dict)
        )
        requested = TaskSupplyRequested.model_validate_json(
            canonical_json({"records": [], **items[0]["content"]})
        )
        assert requested.task_ref.version is not None
        task = TaskRef(
            kind="task", object_id=UUID(requested.task_ref.id), version=requested.task_ref.version
        )
        methods = [
            SolutionRef(kind="solution", object_id=UUID(method.id), version=method.version)
            for method in requested.allowed_method_refs
            if method.version is not None
        ]
        await chapter_methods(db, requested.domain_id, task, methods)
        if await self._exists(db, trigger, scope):
            return answer
        input_id = uuid5(trigger, "task-supply-input")
        if await db.scalar(
            text(
                "SELECT 1 FROM domain.artifact WHERE artifact_id=:id AND domain_id=:domain "
                "AND payload ? 'generation'"
            ),
            {"id": input_id, "domain": requested.domain_id},
        ):
            return Acceptance(
                disposition="accepted",
                arrangement_refs=[
                    Ref(
                        owner="runtime",
                        type="execution",
                        id=str(uuid5(trigger, "generate-task-supply")),
                    )
                ],
            )
        instances = await db.execute(
            text(
                "SELECT i.object_id,v.version,v.content FROM domain.object_identity i "
                "JOIN domain.object_version v "
                "ON (v.object_id,v.version)=(i.object_id,i.head_version) "
                "WHERE i.domain_id=:domain AND i.kind='task_instance' AND NOT v.is_deleted "
                "AND v.content #>> '{task_ref,object_id}' = :task "
                "AND v.content #>> '{task_ref,version}' = :version ORDER BY i.object_id"
            ),
            {
                "domain": requested.domain_id,
                "task": str(task.object_id),
                "version": str(task.version),
            },
        )
        available = [
            InstanceView(
                instance_ref=InstanceRef(object_id=row.object_id, version=row.version),
                content=TaskInstance.model_validate_json(canonical_json(row.content)),
                is_deleted=False,
            )
            for row in instances
        ]
        chosen, unfilled = select_instances(requested, available)
        when, event_id = datetime.now(UTC), uuid4()
        records: list[FactRecord] = []
        supplied: list[SuppliedTask] = []
        for candidate in chosen:
            instance = candidate.instance.instance_ref
            identity = instance.reference()
            check_id = uuid5(trigger, f"{identity.id}:{identity.version}")
            check = _ref("use_check", check_id)
            method_refs = list(
                dict.fromkeys(
                    _ref("solution", method.solution_ref.object_id, method.solution_ref.version)
                    for method in candidate.references
                )
            )
            check_body: dict[str, JsonValue] = {
                "instance_ref": identity.model_dump(mode="json"),
                "purpose": requested.purpose,
                "matched_method_refs": [method.model_dump(mode="json") for method in method_refs],
                "passed": True,
            }
            evidence = _artifact(requested, check_id, "use_check", check_body, when)
            records.append(_record(analysis_facts.ARTIFACT, check_id, evidence))
            supplied.append(
                SuppliedTask(
                    task_instance_ref=identity,
                    content_ref=identity.model_copy(update={"path": "/statement"}),
                    reference_solution_refs=[
                        _ref("reference_solution", method.reference_id, instance.version)
                        for method in candidate.references
                    ],
                    matched_method_refs=method_refs,
                    use_check_ref=check,
                    source="existing",
                )
            )
        saved_input = requested.model_dump(mode="json", exclude={"records"})
        basis = None
        generation = self.generation
        if (
            generation
            and generation.config
            and unfilled
            and requested.exposed_instances is not None
        ):
            domain = requested.domain_id
            definition = TaskDefinition.model_validate(await require_definition(db, domain, task))
            solutions = [
                SolutionDefinition.model_validate(await require_definition(db, domain, method))
                for method in methods
            ]
            basis = Basis(
                scope_id=scope,
                trigger_event_id=trigger,
                requested=requested,
                task=task,
                methods=methods,
                existing=supplied,
                remaining=unfilled.count,
                task_text=definition.model_dump(mode="json"),
                method_text=[item.model_dump(mode="json") for item in solutions],
                seen_statements=[
                    canonical_json(item.content.statement.model_dump(mode="json"))
                    for item in available
                ],
            )
            saved_input["generation"] = basis.model_dump(mode="json")
        required = _artifact(requested, input_id, "input", saved_input, when)
        records.insert(0, _record(analysis_facts.ARTIFACT, input_id, required))
        result = supply_facts.SupplyBatch(
            batch_id=batch_id,
            trigger_event_id=trigger,
            scope_id=scope,
            input_artifact_id=input_id,
            items=supplied,
            unfilled=[unfilled] if unfilled else [],
            completed_event_id=event_id,
            created_at=when,
        )
        input_ref = _ref("supply_input", input_id)
        prepared = supply_facts.SupplyPrepared(
            trigger_event_id=trigger,
            input_artifact_ref=input_ref,
            use_check_refs=[item.use_check_ref for item in supplied],
            records=records,
        )
        completed = DomainTaskSupplyCompleted(
            trigger_event_id=trigger,
            supply_batch_ref=batch,
            result_ref=batch,
            records=[_record(supply_facts.BATCH, batch_id, result)],
        )
        sequence = await lock_scope_sequence(db, SCOPE, scope)
        drafts = [
            EventDraft(
                uuid4(),
                supply_facts.PREPARED,
                1,
                SCOPE,
                scope,
                input_ref,
                prepared.model_dump(mode="json"),
                source_request_id=None,
                causation_event_id=trigger,
            )
        ]
        if basis is None:
            drafts.append(
                EventDraft(
                    event_id,
                    COMPLETED,
                    1,
                    SCOPE,
                    scope,
                    batch,
                    completed.model_dump(mode="json"),
                    source_request_id=None,
                    causation_event_id=trigger,
                )
            )
        events = await self.events.append(
            db,
            ProducerAccess(
                "domain",
                Ref(owner="domain", type="service", id="task_supply"),
                frozenset({(SCOPE, scope)}),
                frozenset({trigger}),
            ),
            drafts,
            commit_id=uuid4(),
            correlation_id=trigger,
            expected_seq={(SCOPE, scope): sequence},
        )
        for event in events:
            await supply_facts.project(db, event)
        if basis and generation:
            work = await generation.accept(db, basis, input_ref)
            return Acceptance(disposition="accepted", arrangement_refs=[work])
        return answer

    @staticmethod
    async def _exists(db: AsyncConnection, trigger: UUID, scope: UUID) -> bool:
        return (
            await db.scalar(
                text(
                    "SELECT 1 FROM domain.supply_batch "
                    "WHERE trigger_event_id=:id AND scope_id=:scope"
                ),
                {"id": trigger, "scope": scope},
            )
            is not None
        )
