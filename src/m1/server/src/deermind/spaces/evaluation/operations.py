"""用正式源事件受理评价，并持久化模型解释及核对结果。"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from deermind.abstractions.ai.contracts import ExecutionConfig
from deermind.abstractions.delivery import Acceptance, EventNotice
from deermind.abstractions.events import EventDraft, FactRecord, InlineContent, ProducerAccess, Ref
from deermind.abstractions.executions import Authorization, Execution, RunInput, State
from deermind.foundation.ai import store as ai_store
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import lock_scope_sequence
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import Caller, Entry, Registry
from deermind.spaces.evaluation import (
    history_conditions,
    interpretation,
    interpretation_facts,
    sequence,
)
from deermind.spaces.evaluation.inputs import (
    ACTOR,
    EvaluationInputs,
    EvaluationMaterials,
    find_prepared,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

ANSWER = "AnswerSubmitted"
TEACHING = "TeachingOpportunityClosed"
OPERATION = "evaluation.evaluate_submission"
WORKFLOW = "evaluation.evaluate_submission.v1"
TEACHING_OPERATION = "evaluation.apply_learning_opportunity"
TEACHING_WORKFLOW = "evaluation.apply_learning_opportunity.v1"
SCOPE = "learning_space"
SOURCES = {
    ANSWER: (OPERATION, WORKFLOW, "answer_event"),
    TEACHING: (TEACHING_OPERATION, TEACHING_WORKFLOW, "teaching_event"),
}

type Configure = Callable[[int], tuple[ExecutionConfig, int]]
LOGGER = logging.getLogger(__name__)


class EvaluationOperations:
    def __init__(
        self, inputs: EvaluationInputs, queue: str, configure: Configure, reader: EventReader
    ) -> None:
        self.inputs = inputs
        self.configure = configure
        self.reader = reader
        self.registry = Registry(
            [
                Entry(
                    "evaluation",
                    operation,
                    "ai_operation",
                    Ref(owner="evaluation", type="operation", id=operation, version=1),
                    workflow,
                    queue,
                    self._lock,
                    self._check,
                    self._finalize,
                )
                for operation, workflow, _source in SOURCES.values()
            ]
        )

    @staticmethod
    async def _lock(_db: AsyncConnection, kind: str, _scope: UUID) -> None:
        # 评价只允许在学习空间内执行，其他范围类型拒绝加锁。
        if kind != SCOPE:
            raise PermissionError("Evaluation only operates on a learning space")

    @staticmethod
    async def _check(
        _db: AsyncConnection, work: Execution, authorization: Authorization, _action: str
    ) -> None:
        expected = "answer_event" if work.entry_ref == OPERATION else "teaching_event"
        # 范围类型、输入归属与类型、受理键、授权依据须与固定触发事件逐项一致。
        if (
            work.scope_kind != SCOPE
            or work.input_ref.owner != "interaction"
            or work.input_ref.type != expected
            or work.input_ref.id != work.acceptance_key
            or authorization.basis_refs != [work.input_ref]
        ):
            raise PermissionError("Evaluation work does not match the fixed trigger")

    @staticmethod
    async def _finalize(
        _db: AsyncConnection, _work: Execution, _state: State, _result: Ref | None
    ) -> None:
        """底座记录技术结果；无候选与技术失败有不同的事实。"""

    async def receive(self, db: AsyncConnection, notice: EventNotice) -> Acceptance:
        # 非学习空间、非可受理事件类型、非 interaction 产出的通知一律忽略。
        if (
            notice.scope_kind != SCOPE
            or notice.event_type not in SOURCES
            or notice.producer != "interaction"
        ):
            return Acceptance(disposition="ignored", arrangement_refs=[])
        scope = notice.scope_id
        prepared = await self.inputs.prepare(scope, notice.event_id)
        await self.advance(db, scope)
        return Acceptance(
            disposition="accepted",
            arrangement_refs=[
                Ref(owner="evaluation", type="evaluation_input", id=str(prepared.record.input_id))
            ],
        )

    async def advance(self, db: AsyncConnection, scope: UUID) -> None:
        event = await sequence.next_source(db, self.reader, scope, tuple(SOURCES))
        # 没有待处理的源事件，直接返回。
        if event is None:
            return
        trigger = event.event_id
        prepared = await find_prepared(db, scope, trigger)
        # 该触发对应的准备记录缺失，跳过。
        if prepared is None:
            return
        # 准备记录的源序号须与源事件序号一致，防止错配历史版本。
        if prepared.source_seq != event.scope_event_seq:
            raise ValueError("Prepared evaluation sequence does not match the source")
        selections = {
            (task.task_ref.object_id, method.method_ref.object_id, method.method_ref.version)
            for task in prepared.input.candidate_scope
            for method in task.methods
        }
        config, seconds = self.configure(max(1, len(selections)))
        operation, _workflow, source_type = SOURCES[event.event_type]
        # 事件映射出的来源类型须与准备记录的作答/教学类型一致。
        if source_type != f"{prepared.source_kind}_event":
            raise ValueError("Prepared evaluation kind does not match the source")
        source = Ref(owner="interaction", type=source_type, id=str(trigger))
        execution_id = uuid5(trigger, operation)
        execution = await store.accept(
            db,
            self.registry,
            Caller(ACTOR, "evaluation", frozenset({(SCOPE, scope)}), frozenset({"accept"})),
            entry_name=operation,
            scope_kind=SCOPE,
            scope_id=scope,
            acceptance_key=str(trigger),
            input_ref=source,
            seconds=seconds,
            basis_refs=[source],
            ai_config_ref=execution_id,
        )
        await ai_store.pin(db, execution, config)
        await sequence.begin(db, scope, event)

    async def reconcile(self, stopped: asyncio.Event, interval: float) -> None:
        # 后台轮询：直到停止信号置位，每轮扫描有待处理触发的空间并推进评价。
        while not stopped.is_set():
            try:
                async with self.inputs.engine.connect() as db:
                    scopes = (
                        await db.scalars(
                            text("""
                        SELECT DISTINCT i.scope_id FROM evaluation.evaluation_input i
                        JOIN evaluation.evaluation_progress p USING(scope_id)
                        WHERE p.active_trigger_event_id IS NULL
                        AND i.source_seq>p.scanned_through_seq
                    """)
                        )
                    ).all()
                for scope in scopes:
                    async with self.inputs.engine.begin() as db:
                        await self.advance(db, scope)
            except Exception:
                # 单轮扫描异常只记录日志，不中断后台循环。
                LOGGER.exception(
                    "评价队列检查失败", extra={"error_code": "EVALUATION_QUEUE_FAILED"}
                )
            try:
                # 等待停止信号；超时则进入下一轮，被信号唤醒则退出循环。
                await asyncio.wait_for(stopped.wait(), timeout=interval)
            except TimeoutError:
                continue

    async def materials(self, run: RunInput) -> EvaluationMaterials:
        async with self.inputs.engine.begin() as db:
            work = await store.active(db, self.registry, run, "step")
        return await self.inputs.prepare(work.scope_id, UUID(work.input_ref.id))

    async def history(self, bundle: EvaluationMaterials) -> history_conditions.History:
        # 历史条件只针对作答类记录，教学类直接返回空结论。
        if bundle.source.source_kind != "answer":
            return history_conditions.History({})
        async with self.inputs.engine.connect() as db:
            return await history_conditions.collect(
                db, bundle, self.inputs.sources, self.inputs.prior_questions
            )

    async def save(
        self,
        run: RunInput,
        candidate_id: UUID,
        candidate: interpretation.Interpretation,
        publish_mastery: bool = False,
    ) -> Ref:
        identity = uuid5(run.execution_id, "interpretation")
        result = Ref(owner="evaluation", type="interpretation", id=str(identity))
        async with self.inputs.engine.connect() as db:
            work = await store.load(db, run.execution_id)
            # 执行已完成且仍是本次尝试：幂等重入，核对结果引用后直接返回。
            if work.state == "completed" and work.active_attempt_id == run.attempt_id:
                if work.result_ref != result:
                    raise ValueError("Evaluation has a different saved result")
                return result
        bundle = await self.materials(run)
        history = await self.history(bundle)
        validated = interpretation.check(bundle, candidate, history.checks)
        record = interpretation_facts.InterpretationRecord(
            interpretation_id=identity,
            input_ref=bundle.record.input_id,
            ai_call_ref=Ref(owner="ai", type="candidate", id=str(candidate_id)),
            contract_ref=Ref(
                owner="evaluation",
                type="ai_schema",
                id=bundle.record.input.interpretation_contract_ref,
                version=1,
            ),
            candidate=candidate,
            validation=validated,
            created_at=datetime.now(UTC),
        )
        event = interpretation_facts.InterpretationPrepared(
            interpretation_ref=result,
            evaluation_input_ref=Ref(
                owner="evaluation", type="evaluation_input", id=str(record.input_ref)
            ),
            records=[
                FactRecord(
                    record_id=result.id,
                    record_type=interpretation_facts.TABLE,
                    schema_version=1,
                    content=InlineContent(storage="inline", value=record.model_dump(mode="json")),
                )
            ],
        )
        scope, trigger = (SCOPE, work.scope_id), bundle.record.trigger_event_id
        access = ProducerAccess("evaluation", ACTOR, frozenset({scope}), frozenset({trigger}))
        draft = EventDraft(
            uuid4(),
            interpretation_facts.PREPARED,
            1,
            *scope,
            result,
            event.model_dump(mode="json"),
            None,
            causation_event_id=trigger,
            source_execution_ref=run.execution_id,
        )
        prepared = await self.inputs.attachments.prepare(self.inputs.events, access, (draft,))
        async with self.inputs.engine.begin() as db:
            current = await store.lock_owned(db, self.registry, run.execution_id)
            # 加锁后再次确认已完成且为本次尝试，避免并发重复落库。
            if current.state == "completed" and current.active_attempt_id == run.attempt_id:
                if current.result_ref != result:
                    raise ValueError("Evaluation has a different saved result")
                return result
            await store.active(db, self.registry, run, "finish")
            # 该执行已存在解释记录，视为已保存，直接返回结果引用。
            if await self.saved_interpretation(db, run.execution_id):
                return result
            sequence = await lock_scope_sequence(db, *scope)
            (committed,) = await self.inputs.events.append(
                db,
                access,
                prepared,
                commit_id=uuid4(),
                correlation_id=trigger,
                expected_seq={scope: sequence},
            )
            await interpretation_facts.project(db, committed)
            # 本次不发布掌握快照时，直接把执行标记完成；发布路径由后续流程处理。
            if not publish_mastery:
                await commands.complete(db, self.registry, run, result)
        return result

    @staticmethod
    async def saved_interpretation(db: AsyncConnection, execution_id: UUID) -> Ref | None:
        identity = uuid5(execution_id, "interpretation")
        # 解释记录已落库则返回其引用，否则表示尚未保存。
        if await db.scalar(
            text("SELECT 1 FROM evaluation.interpretation WHERE interpretation_id=:id"),
            {"id": identity},
        ):
            return Ref(owner="evaluation", type="interpretation", id=str(identity))
        return None

    async def checkpoint(self, run: RunInput) -> Ref | None:
        async with self.inputs.engine.begin() as db:
            await store.active(db, self.registry, run, "step")
            return await self.saved_interpretation(db, run.execution_id)
