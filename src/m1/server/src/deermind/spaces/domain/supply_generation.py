"""库存不足时保留本次供题事实，按已固定条件执行生成与复核。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    FactModel,
    FactRecord,
    InlineContent,
    PreparedEvents,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.executions import Authorization, Execution, RunInput, State
from deermind.abstractions.task_supply import (
    COMPLETED,
    DomainTaskSupplyCompleted,
    SuppliedTask,
    TaskSupplyRequested,
    UnfilledSupply,
)
from deermind.foundation.ai import store as ai_store
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.store import EventStore, lock_scope_sequence
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Caller, Entry, Registry
from deermind.spaces.domain import analysis_facts, supply_facts
from deermind.spaces.domain.generated_tasks import (
    GeneratedQuestions,
    QualityChecks,
    accepted_numbers,
    materialize,
)
from deermind.spaces.domain.instance_facts import InstanceVersion, project_instance
from deermind.spaces.domain.instances import instance_event, validate_instance
from deermind.spaces.domain.public import SolutionRef, TaskInstance, TaskRef

OPERATION = "domain.supply_task"
WORKFLOW = OPERATION
ACTOR = Ref(owner="domain", type="service", id="task_supply")


class Basis(FactModel):
    scope_id: UUID
    trigger_event_id: UUID
    requested: TaskSupplyRequested
    task: TaskRef
    methods: list[SolutionRef]
    existing: list[SuppliedTask]
    remaining: int
    task_text: dict[str, JsonValue]
    method_text: list[dict[str, JsonValue]]
    seen_statements: list[str]


def reference(kind: str, identity: UUID) -> Ref:
    return Ref(owner="domain", type=kind, id=str(identity))


def record(kind: str, identity: UUID, body: FactModel) -> FactRecord:
    return FactRecord(
        record_id=str(identity),
        record_type=kind,
        schema_version=1,
        content=InlineContent(storage="inline", value=body.model_dump(mode="json")),
    )


class GenerateSupply:
    def __init__(
        self,
        engine: AsyncEngine,
        events: EventStore,
        attachments: FactAttachments,
        queue: str,
        config: ExecutionConfig | None,
    ) -> None:
        self.engine = engine
        self.events = events
        self.attachments = attachments
        self.config = config
        self.registry = Registry(
            [
                Entry(
                    "domain",
                    OPERATION,
                    "ai_operation",
                    Ref(owner="domain", type="operation", id=OPERATION, version=1),
                    WORKFLOW,
                    queue,
                    self._lock,
                    self._check,
                    self._finalize,
                )
            ]
        )

    @staticmethod
    async def _lock(db: AsyncConnection, kind: str, identity: UUID) -> None:
        # 供题锁定必须落在固定领域身份上。
        if kind != "domain" or not await db.scalar(
            text("SELECT object_id FROM domain.object_identity WHERE object_id=:id FOR UPDATE"),
            {"id": identity},
        ):
            raise PermissionError("Supply requires the fixed domain")

    async def _check(
        self, db: AsyncConnection, work: Execution, _grant: Authorization, action: str
    ) -> None:
        if action in {"read", "cancel"}:
            return
        value = await self._basis(db, work)
        if value.requested.domain_id != work.scope_id:
            # 供题依据归属另一领域，拒绝。
            raise PermissionError("Supply context belongs to another domain")

    @staticmethod
    async def _finalize(
        _db: AsyncConnection, _work: Execution, _state: State, _result: Ref | None
    ) -> None:
        """技术失败保留执行记录，结果为空时才记录业务缺口。"""

    @staticmethod
    async def _basis(db: AsyncConnection, work: Execution) -> Basis:
        body = await db.scalar(
            text(
                "SELECT payload->'generation' FROM domain.artifact "
                "WHERE artifact_id=:id AND domain_id=:domain AND kind='input'"
            ),
            {"id": UUID(work.input_ref.id), "domain": work.scope_id},
        )
        if body is None:
            # 供题输入产物缺失，无法恢复依据。
            raise LookupError("Supply input is missing")
        return Basis.model_validate_json(canonical_json(body))

    async def accept(self, db: AsyncConnection, stored: Basis, input_ref: Ref) -> Ref:
        """结果未完成时同一触发重投仍返回原执行。"""
        if self.config is None:
            # 未配置模型，无法启动生成执行。
            raise ValueError("Task generation is not configured")
        domain = stored.requested.domain_id
        work_id = uuid5(stored.trigger_event_id, "generate-task-supply")
        execution = await store.accept(
            db,
            self.registry,
            Caller(ACTOR, "domain", frozenset({("domain", domain)}), frozenset({"accept"})),
            entry_name=OPERATION,
            scope_kind="domain",
            scope_id=domain,
            acceptance_key=str(stored.trigger_event_id),
            input_ref=input_ref,
            seconds=600,
            basis_refs=[stored.requested.task_ref, *stored.requested.allowed_method_refs],
            ai_config_ref=work_id,
        )
        await ai_store.pin(db, execution, self.config)
        return Ref(owner="runtime", type="execution", id=str(work_id))

    async def basis(self, run: RunInput) -> Basis:
        async with self.engine.begin() as db:
            execution = await store.active(db, self.registry, run, "step")
            return await self._basis(db, execution)

    async def save(
        self,
        run: RunInput,
        proposed: GeneratedQuestions,
        checks: QualityChecks,
        check_candidate: UUID,
    ) -> None:
        async with self.engine.connect() as db:
            execution = await store.load(db, run.execution_id)
            if execution.state == "completed":
                # 已完成的执行不重复落结果。
                return
            basis = await self._basis(db, execution)
        trigger = basis.trigger_event_id
        domain = execution.scope_id
        now = datetime.now(UTC)
        identities: list[TaskInstance] = []
        questions = proposed.questions
        accepted = accepted_numbers(checks, len(questions))
        seen = set(basis.seen_statements)
        if len(questions) <= basis.remaining:
            # 候选数量不超缺口，逐条物化通过检查的题目。
            for number in accepted:
                try:
                    task = materialize(
                        questions[number - 1], basis.task, basis.methods, trigger, number
                    )
                except ValueError:
                    # 物化校验失败，跳过该候选。
                    continue
                statement = canonical_json(task.statement.model_dump(mode="json"))
                if statement in seen:
                    # 题面与既有题目重复，去重。
                    continue
                seen.add(statement)
                identities.append(task)
        prepared, result, versions = await self._prepare(
            basis, execution, identities, check_candidate, now
        )
        async with self.engine.begin() as db:
            saved = await store.lock_owned(db, self.registry, run.execution_id)
            if saved.state == "completed":
                # 加锁后发现已完成，放弃重复提交。
                return
            await store.active(db, self.registry, run, "finish")
            for instance in identities:
                await validate_instance(db, domain, instance)
            scopes = {(draft.scope_kind, draft.scope_id) for draft in prepared.drafts}
            sequences = {
                key: await lock_scope_sequence(db, *key)
                for key in sorted(scopes, key=lambda value: (value[0], str(value[1])))
            }
            for event in await self.events.append(
                db,
                prepared.access,
                prepared,
                commit_id=uuid4(),
                expected_seq=sequences,
                correlation_id=trigger,
            ):
                if instance := versions.get(event.draft.event_id):
                    # 题目版本事件投影实例表。
                    await project_instance(db, event, instance)
                else:
                    # 其余为供题批次/检查事件。
                    await supply_facts.project(db, event)
            await commands.complete(db, self.registry, run, result)

    async def _prepare(
        self,
        basis: Basis,
        work: Execution,
        new: list[TaskInstance],
        check_candidate: UUID,
        now: datetime,
    ) -> tuple[PreparedEvents, Ref, dict[UUID, InstanceVersion]]:
        trigger, scope, domain = basis.trigger_event_id, basis.scope_id, work.scope_id
        requested = basis.requested
        input_id = UUID(work.input_ref.id)
        input_ref = reference("supply_input", input_id)
        check_records: list[FactRecord] = []
        items = list(basis.existing)
        drafts: list[EventDraft] = []
        versions: dict[UUID, InstanceVersion] = {}
        for number, question in enumerate(new, 1):
            # 为每道新题生成检查产物、实例事件与供题条目。
            identity = uuid5(trigger, f"generated-question:{number}")
            check_id = uuid5(trigger, f"generated-check:{number}")
            check_ref = reference("use_check", check_id)
            method = question.reference_solutions[0]
            artifact = analysis_facts.AnalysisArtifact(
                artifact_id=check_id,
                domain_id=domain,
                kind="use_check",
                input_ref=input_ref,
                definition_refs=[requested.task_ref, *requested.allowed_method_refs],
                payload={"ai_candidate_ref": str(check_candidate), "result": "passed"},
                rule_ref=Ref(owner="domain", type="rule", id="generated_supply_quality", version=1),
                model_call_ref=None,
                command_ref=requested.request_ref,
                created_at=now,
            )
            check_records.append(record(analysis_facts.ARTIFACT, check_id, artifact))
            event, instance = instance_event(
                domain,
                identity,
                None,
                question,
                ACTOR,
                trigger,
                "供题通过独立检查",
                "create",
                [check_ref],
            )
            drafts.append(event)
            versions[event.event_id] = instance
            fixed = Ref(
                owner="domain", type="task_instance", id=str(identity), version=instance.version
            )
            items.append(
                SuppliedTask(
                    task_instance_ref=fixed,
                    content_ref=fixed.model_copy(update={"path": "/statement"}),
                    reference_solution_refs=[
                        Ref(
                            owner="domain",
                            type="reference_solution",
                            id=str(method.reference_id),
                            version=instance.version,
                        )
                    ],
                    matched_method_refs=[
                        Ref(
                            owner="domain",
                            type="solution",
                            id=str(method.solution_ref.object_id),
                            version=method.solution_ref.version,
                        )
                    ],
                    use_check_ref=check_ref,
                    source="generated",
                )
            )
        if check_records:
            # 有生成检查时，先落检查事件。
            validated = supply_facts.SupplyPrepared(
                trigger_event_id=trigger,
                input_artifact_ref=input_ref,
                use_check_refs=[item.use_check_ref for item in items if item.source == "generated"],
                records=check_records,
            )
            drafts.insert(
                0,
                EventDraft(
                    uuid4(),
                    supply_facts.CHECKED,
                    1,
                    "learning_space",
                    scope,
                    input_ref,
                    validated.model_dump(mode="json"),
                    None,
                    causation_event_id=trigger,
                ),
            )
        batch_id, event_id = uuid5(trigger, "task-supply-batch"), uuid4()
        result = reference("supply_batch", batch_id)
        still_missing = basis.remaining - len(new)
        missing = (
            [
                UnfilledSupply(
                    count=still_missing,
                    condition=requested.assessment_constraints,
                    reason="no_eligible_instance",
                    retryable=True,
                )
            ]
            if still_missing
            else []  # 凑满数量则无缺口
        )
        projection = supply_facts.SupplyBatch(
            batch_id=batch_id,
            trigger_event_id=trigger,
            scope_id=scope,
            input_artifact_id=input_id,
            items=items,
            unfilled=missing,
            completed_event_id=event_id,
            created_at=now,
        )
        completed = DomainTaskSupplyCompleted(
            trigger_event_id=trigger,
            supply_batch_ref=result,
            result_ref=result,
            records=[record(supply_facts.BATCH, batch_id, projection)],
        )
        drafts.append(
            EventDraft(
                event_id,
                COMPLETED,
                1,
                "learning_space",
                scope,
                result,
                completed.model_dump(mode="json"),
                None,
                causation_event_id=trigger,
            )
        )
        access = ProducerAccess(
            "domain",
            ACTOR,
            frozenset((item.scope_kind, item.scope_id) for item in drafts),
            frozenset({trigger}),
        )
        prepared = await self.attachments.prepare(self.events, access, tuple(drafts))
        return prepared, result, versions
