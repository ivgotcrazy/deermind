"""E01-18 隔离用例的事实、所有者投影和执行登记。"""

import logging
import os
from hashlib import sha256
from uuid import UUID, uuid4

from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import (
    EventDraft,
    EventPayload,
    EventRegistration,
    FactModel,
    FactRecord,
    InlineContent,
    ProducerAccess,
    Ref,
)
from deermind.abstractions.executions import Authorization, Execution, RunInput, State
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.executions.contracts import Entry, Registry
from deermind.foundation.system.projections.receipts import application
from execution_worker import lock_owner
from nats.aio.client import Client
from nats.errors import Error as NatsError
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

ACTION = "test.foundation_chain"
ENTRY_NAME = "product.foundation_chain"
WORKFLOW_NAME = "foundation-chain"
RESOURCE_KIND = "account"
VIEW = "foundation_chain"
INPUT = "四分之一合成输入"
INPUT_EVENT = "FoundationChainInputAccepted"
RESULT_EVENT = "FoundationChainResultSaved"
RESULT_KIND = "foundation_chain_result"
RESULT_TABLE = "product.foundation_chain_results"
PAYLOAD = b"foundation-chain" * 12000
EXPECTED_SHA = sha256(PAYLOAD).hexdigest()
LOGGER = logging.getLogger("runtime")


class InputPayload(EventPayload):
    text: str = Field(min_length=1, max_length=120)


class ResultFact(FactModel):
    execution_id: UUID
    input_event_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def account_ref(account_id: UUID) -> Ref:
    return Ref(owner="product", type="account", id=str(account_id))


def input_ref(event_id: UUID) -> Ref:
    return Ref(owner="runtime", type="event", id=str(event_id))


def result_ref(execution_id: UUID) -> Ref:
    return Ref(owner="product", type=RESULT_KIND, id=str(execution_id), path=EXPECTED_SHA)


def validate_input(draft: EventDraft, payload: EventPayload) -> None:
    if payload.records or draft.owner_ref != account_ref(draft.scope_id):
        raise ValueError("The fixture input must belong to its account")


def decode_result(payload: EventPayload) -> ResultFact:
    if len(payload.records) != 1:
        raise ValueError("One owner result record is expected")
    record = payload.records[0]
    if record.record_type != RESULT_TABLE or not isinstance(record.content, InlineContent):
        raise ValueError("The owner result must contain an inline projection record")
    return ResultFact.model_validate_json(canonical_json(record.content.value))


def validate_result(draft: EventDraft, payload: EventPayload) -> None:
    result = decode_result(payload)
    if (
        draft.owner_ref != account_ref(draft.scope_id)
        or draft.causation_event_id != result.input_event_id
        or draft.source_execution_ref != result.execution_id
    ):
        raise ValueError("The result must retain its original input and execution identity")


INPUT_REGISTRATION = EventRegistration(
    INPUT_EVENT, 1, "product", RESOURCE_KIND, InputPayload, validate_input
)
RESULT_REGISTRATION = EventRegistration(
    RESULT_EVENT,
    1,
    "product",
    RESOURCE_KIND,
    EventPayload,
    validate_result,
    {(RESULT_TABLE, 1): ResultFact},
)


async def account_sequence(connection: AsyncConnection, account_id: UUID) -> int:
    return int(
        await connection.scalar(
            text(
                "SELECT last_seq FROM runtime.scope_event_heads "
                "WHERE scope_kind='account' AND scope_id=:account"
            ),
            {"account": account_id},
        )
        or 0
    )


async def read_input(engine: AsyncEngine, run: RunInput) -> str:
    """Worker 只读本次获准执行关联的已提交合成原文。"""
    async with engine.connect() as connection:
        body = await connection.scalar(
            text(
                "SELECT event.payload ->> 'text' FROM runtime.events AS event "
                "JOIN runtime.executions AS execution ON execution.scope_id=event.scope_id "
                "WHERE event.event_id=:event AND event.event_type=:event_type "
                "AND execution.execution_id=:execution AND execution.entry_ref=:entry "
                "AND execution.input_ref ->> 'id'=CAST(event.event_id AS text)"
            ),
            {
                "event": UUID(run.input_ref.id),
                "event_type": INPUT_EVENT,
                "execution": run.execution_id,
                "entry": ENTRY_NAME,
            },
        )
    if body != INPUT:
        raise ValueError("Missing the fixed fixture input")
    return body


async def finalize(
    connection: AsyncConnection, execution: Execution, state: State, result: Ref | None
) -> None:
    """随执行终态一起保存结果事实和所有者投影。"""
    if state != "completed":
        return
    if result != result_ref(execution.execution_id):
        raise ValueError("The verified result differs from the expected SHA-256")
    assert result is not None and result.path is not None
    input_event = UUID(execution.input_ref.id)
    receipt = await connection.scalar(
        text("SELECT correlation_id FROM runtime.events WHERE event_id=:event"),
        {"event": input_event},
    )
    assert isinstance(receipt, UUID)
    account = account_ref(execution.scope_id)
    fact = ResultFact(
        execution_id=execution.execution_id, input_event_id=input_event, sha256=result.path
    )
    payload = EventPayload(
        records=[
            FactRecord(
                record_id="result",
                record_type=RESULT_TABLE,
                schema_version=1,
                content=InlineContent(storage="inline", value=fact.model_dump(mode="json")),
            )
        ]
    )
    scope = (RESOURCE_KIND, execution.scope_id)
    (event,) = await EventStore([RESULT_REGISTRATION]).append(
        connection,
        ProducerAccess("product", account, frozenset({scope}), frozenset({input_event})),
        [
            EventDraft(
                uuid4(),
                RESULT_EVENT,
                1,
                *scope,
                account,
                payload.model_dump(mode="json"),
                None,
                causation_event_id=input_event,
                source_execution_ref=execution.execution_id,
            )
        ],
        commit_id=uuid4(),
        correlation_id=receipt,
        expected_seq={scope: await account_sequence(connection, execution.scope_id)},
    )
    async with application(
        connection, "product.foundation_chain", 1, event.draft.event_id
    ) as apply:
        assert apply
        projected = decode_result(event.payload)
        await connection.execute(
            text(
                "INSERT INTO product.foundation_chain_results "
                "(execution_id,input_event_id,sha256,source_event_id) "
                "VALUES (:execution_id,:input_event_id,:sha256,:source_event_id)"
            ),
            {**projected.model_dump(), "source_event_id": event.draft.event_id},
        )


def registry(scope: UUID, queue: str) -> Registry:
    async def check(
        _connection: AsyncConnection, execution: Execution, _grant: Authorization, _action: str
    ) -> None:
        if (execution.scope_kind, execution.scope_id) != (RESOURCE_KIND, scope):
            raise PermissionError("Execution belongs to a different fixture account")

    return Registry(
        [
            Entry(
                "product",
                ENTRY_NAME,
                "handler",
                Ref(owner="product", type="implementation", id=ENTRY_NAME, revision=1),
                WORKFLOW_NAME,
                queue,
                lock_owner,
                check,
                finalize,
            )
        ]
    )


async def publish_result(engine: AsyncEngine, execution_id: UUID, deployment: str) -> None:
    """只在结果提交后向本轮隔离的 Core NATS 主题播报事实身份。"""
    async with engine.connect() as connection:
        event_id = await connection.scalar(
            text(
                "SELECT source_event_id FROM product.foundation_chain_results "
                "WHERE execution_id=:id"
            ),
            {"id": execution_id},
        )
    assert isinstance(event_id, UUID)
    client = Client()
    try:
        await client.connect(
            servers=[os.environ["M1_TEST_NATS_ADDRESS"]],
            user="maintenance",
            password=os.environ["M1_TEST_NATS_PASSWORD"],
            connect_timeout=5,
            max_reconnect_attempts=0,
        )
        await client.publish(f"dm.{deployment}.view_changed", str(event_id).encode("ascii"))
        await client.flush(timeout=5)
    except (NatsError, OSError, TimeoutError) as error:
        LOGGER.warning(
            "测试结果已保存，实时提示暂不可用",
            extra={"event_id": str(event_id), "error_code": type(error).__name__},
        )
    finally:
        await client.close()
