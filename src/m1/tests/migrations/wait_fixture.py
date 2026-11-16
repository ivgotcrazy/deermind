"""E01-14隔离业务：生产一份结果，消费方自行定义探测与接续，不接正式教学。"""

import asyncio
from datetime import timedelta
from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import (
    EventDraft,
    EventPayload,
    EventRegistration,
    ProducerAccess,
    Ref,
)
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.executions import store
from deermind.foundation.system.executions.contracts import (
    Authorization,
    Caller,
    Entry,
    Execution,
    Registry,
    RunInput,
    State,
)
from deermind.foundation.system.waits.contracts import (
    Condition,
    Match,
    Policies,
    Policy,
    Publication,
    ResultKey,
    Wait,
    WaitCall,
)
from deermind.foundation.system.waits.results import ResultPolicy, Results
from deermind.foundation.system.waits.service import Waits
from deermind.infrastructure.temporal.waits import WaitSignals
from execution_worker import ActivityOptions, lock_owner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import workflow
from temporalio.common import RetryPolicy

POLICY_REF = Ref(owner="interaction", type="wait_policy", id="test-result", revision=1)


class Fixture:
    def __init__(self, scope: UUID, queue: str) -> None:
        self.scope, self.queue = scope, queue
        self.fail_handle = False
        self.fail_probe = False
        self.probe_delay_once = 0.0
        self.entries = Registry(
            [
                Entry(
                    owner,
                    owner + ".wait_test",
                    "handler",
                    Ref(owner=owner, type="implementation", id="wait-test", revision=1),
                    "test.wait",
                    queue,
                    lock_owner,
                    self.check,
                    self.finalize,
                )
                for owner in ("product", "interaction")
            ]
        )
        self.results = Results(
            self.entries,
            [ResultPolicy("product", "test_result", frozenset({"interaction"}), self.check_result)],
        )
        self.policies = Policies(
            [
                Policy(
                    POLICY_REF,
                    frozenset({"TestResultPublished"}),
                    frozenset({"learning_space"}),
                    "interaction.test_matched",
                    "interaction.test_timeout",
                    self.probe,
                    self.handle,
                )
            ]
        )
        self.waits = Waits(self.entries, self.policies, maximum_seconds=300)

    def caller(self, owner: str) -> Caller:
        return Caller(
            Ref(owner="runtime", type="operator", id="test"),
            owner,
            frozenset({("learning_space", self.scope)}),
            frozenset({"accept", "read", "retry", "cancel"}),
        )

    async def check(
        self,
        connection: AsyncConnection,
        execution: Execution,
        authorization: Authorization,
        action: str,
    ) -> None:
        if execution.scope_id != self.scope:
            raise PermissionError("Wrong test resource")

    async def finalize(
        self, connection: AsyncConnection, execution: Execution, state: State, result: Ref | None
    ) -> None:
        """本例的业务效果由接续函数保存，无额外收尾。"""

    async def check_result(
        self, connection: AsyncConnection, execution: Execution, result: Publication
    ) -> None:
        body = await connection.scalar(
            text("SELECT payload FROM runtime.events WHERE event_id=:id"), {"id": result.event_id}
        )
        if body["result"] != result.payload:
            raise ValueError("Publication differs from its fact")

    async def accept(self, connection: AsyncConnection, owner: str, key: str) -> RunInput:
        saved = await store.accept(
            connection,
            self.entries,
            self.caller(owner),
            entry_name=owner + ".wait_test",
            scope_kind="learning_space",
            scope_id=self.scope,
            acceptance_key=key,
            input_ref=Ref(owner=owner, type="test_input", id=key),
            seconds=180,
            basis_refs=[self.caller(owner).actor],
        )
        return await self.run_input(connection, saved)

    async def run_input(self, connection: AsyncConnection, saved: Execution) -> RunInput:
        assert saved.active_attempt_id is not None
        current = await store.attempt(connection, saved.active_attempt_id)
        return RunInput(
            execution_id=saved.execution_id,
            attempt_id=current.attempt_id,
            input_ref=saved.input_ref,
            implementation_ref=saved.implementation_ref,
            ai_config_ref=saved.ai_config_ref,
            deadline_at=current.deadline_at,
        )

    async def fact(
        self, connection: AsyncConnection, run: RunInput, *, result: bool = False
    ) -> UUID:
        identity = uuid4()
        name = "TestResultPublished" if result else "TestResultRequested"
        sequence = await connection.scalar(
            text(
                "SELECT last_seq FROM runtime.scope_event_heads "
                "WHERE scope_kind='learning_space' AND scope_id=:id"
            ),
            {"id": self.scope},
        )
        registration = EventRegistration(
            name, 1, "product", "learning_space", Payload, validate_payload
        )
        await EventStore([registration]).append(
            connection,
            ProducerAccess(
                "product", self.caller("product").actor, frozenset({("learning_space", self.scope)})
            ),
            [
                EventDraft(
                    identity,
                    name,
                    1,
                    "learning_space",
                    self.scope,
                    run.input_ref,
                    Payload(records=[], result={"value": "ready"}).model_dump(mode="json"),
                    str(run.execution_id),
                    source_execution_ref=run.execution_id,
                )
            ],
            commit_id=uuid4(),
            correlation_id=run.execution_id,
            expected_seq={("learning_space", self.scope): sequence or 0},
        )
        return identity

    async def setup(self, connection: AsyncConnection) -> tuple[RunInput, RunInput, ResultKey]:
        producer = await self.accept(connection, "product", "producer")
        consumer = await self.accept(connection, "interaction", "consumer")
        trigger = await self.fact(connection, producer)
        key = ResultKey(
            scope_id=self.scope,
            trigger_event_id=trigger,
            producer="product",
            result_kind="test_result",
        )
        await self.results.expect(connection, producer, key)
        return producer, consumer, key

    async def publish(
        self, connection: AsyncConnection, producer: RunInput, key: ResultKey
    ) -> Publication:
        event = await self.fact(connection, producer, result=True)
        return await self.results.publish(
            connection,
            producer,
            key,
            event_id=event,
            result_ref=Ref(owner="product", type="test_result", id=str(event)),
            payload={"value": "ready"},
            publication_refs=[],
        )

    async def register(
        self,
        connection: AsyncConnection,
        run: RunInput,
        key: ResultKey,
        *,
        seconds: float = 30,
        step: str = "wait",
    ) -> Wait:
        now = await connection.scalar(text("SELECT clock_timestamp()"))
        return await self.waits.register(
            connection,
            run,
            step_key=step,
            owner=run.input_ref,
            condition=Condition(
                event_types=["TestResultPublished"],
                scope_kind="learning_space",
                scope_id=self.scope,
                result_key=key,
            ),
            probe_ref=POLICY_REF,
            deadline=now + timedelta(seconds=seconds),
            reserve_seconds=10,
        )

    async def probe(
        self, connection: AsyncConnection, execution: Execution, condition: Condition
    ) -> Match | None:
        if self.fail_probe:
            raise RuntimeError("Test read outage")
        assert condition.result_key is not None
        found = await self.results.read(
            connection, self.caller("interaction"), "learning_space", condition.result_key
        )
        if self.probe_delay_once:
            delay, self.probe_delay_once = self.probe_delay_once, 0.0
            await asyncio.sleep(delay)
        if found.publication:
            return Match(
                event_id=found.publication.event_id, result_ref=found.publication.result_ref
            )
        return None

    async def handle(self, connection: AsyncConnection, execution: Execution, wait: Wait) -> Ref:
        await connection.execute(
            text("INSERT INTO interaction.wait_effect (id,resolution) VALUES (:id,:value)"),
            {"id": wait.resume_action_id, "value": wait.resolution},
        )
        if self.fail_handle:
            raise ValueError("Deliberate failure after owner write")
        return Ref(owner="interaction", type="wait_effect", id=str(wait.resume_action_id))


class Payload(EventPayload):
    result: dict[str, str]


def validate_payload(draft: EventDraft, payload: EventPayload) -> None:
    if not isinstance(payload, Payload):
        raise ValueError("Wrong test payload")


@workflow.defn(name="test.wait", sandboxed=False)
class WaitingWorkflow:
    """真实Temporal的最小消费流程；等待期间Activity槽位全部释放。"""

    def __init__(self) -> None:
        self.signals = WaitSignals()

    @workflow.signal(name="runtime.wait_changed")
    def changed(self, identity: str) -> None:
        self.signals.receive(identity)

    @workflow.run
    async def run(self, body: str) -> str:
        run = RunInput.model_validate_json(body)
        options = ActivityOptions(
            start_to_close_timeout=timedelta(seconds=10),
            schedule_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        wait_id = await workflow.execute_activity(
            "test.find_wait", body, result_type=str, **options
        )
        result = await self.signals.resume(
            WaitCall(run=run, wait_id=UUID(wait_id)),
            activity_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        assert result.handling_receipt_ref is not None
        await workflow.execute_activity(
            "runtime.execution_completed",
            args=[body, result.handling_receipt_ref.model_dump_json()],
            **options,
        )
        return result.state
