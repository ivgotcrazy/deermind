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
        if kind != SCOPE:
            raise PermissionError("Evaluation only operates on a learning space")

    @staticmethod
    async def _check(
        _db: AsyncConnection, work: Execution, authorization: Authorization, _action: str
    ) -> None:
        expected = "answer_event" if work.entry_ref == OPERATION else "teaching_event"
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
        if event is None:
            return
        trigger = event.event_id
        prepared = await find_prepared(db, scope, trigger)
        if prepared is None:
            return
        if prepared.source_seq != event.scope_event_seq:
            raise ValueError("Prepared evaluation sequence does not match the source")
        selections = {
            (task.task_ref.object_id, method.method_ref.object_id, method.method_ref.version)
            for task in prepared.input.candidate_scope
            for method in task.methods
        }
        config, seconds = self.configure(max(1, len(selections)))
        operation, _workflow, source_type = SOURCES[event.event_type]
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
                LOGGER.exception(
                    "评价队列检查失败", extra={"error_code": "EVALUATION_QUEUE_FAILED"}
                )
            try:
                await asyncio.wait_for(stopped.wait(), timeout=interval)
            except TimeoutError:
                continue

    async def materials(self, run: RunInput) -> EvaluationMaterials:
        async with self.inputs.engine.begin() as db:
            work = await store.active(db, self.registry, run, "step")
        return await self.inputs.prepare(work.scope_id, UUID(work.input_ref.id))

    async def history(self, bundle: EvaluationMaterials) -> history_conditions.History:
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
            if current.state == "completed" and current.active_attempt_id == run.attempt_id:
                if current.result_ref != result:
                    raise ValueError("Evaluation has a different saved result")
                return result
            await store.active(db, self.registry, run, "finish")
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
            if not publish_mastery:
                await commands.complete(db, self.registry, run, result)
        return result

    @staticmethod
    async def saved_interpretation(db: AsyncConnection, execution_id: UUID) -> Ref | None:
        identity = uuid5(execution_id, "interpretation")
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
