"""Isolated Temporal workflows for E01-16. Model and tool responses are synthetic."""

import asyncio
import hashlib
from datetime import timedelta
from pathlib import Path

from deermind.bootstrap.settings import Settings
from deermind.bootstrap.temporal import connect_temporal
from deermind.infrastructure.database.connection import application_engine
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow, TemporalDurability
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import URL
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

IMAGE = b"fixture-page-image" * (16 * 1024)
TOOL_RESULT = "fixture-tool-data" * (16 * 1024)
MODEL_RESULT = "fixture-model-result" * (16 * 1024)
NEAR_LIMIT_BYTES = 63 * 1024 * 1024
PARALLEL_ACTIVITIES = 4
ACTIVITY_TIMEOUT = timedelta(seconds=75)
NO_RETRY = RetryPolicy(maximum_attempts=1)


def model_reply(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    parts = [part for msg in messages if isinstance(msg, ModelRequest) for part in msg.parts]
    for part in parts:
        if isinstance(part, UserPromptPart) and not isinstance(part.content, str):
            if any(
                isinstance(value, BinaryContent) and value.data == IMAGE for value in part.content
            ):
                break
    else:
        raise ValueError("Model did not receive the intact synthetic image")
    if any(isinstance(part, ToolReturnPart) and part.content == TOOL_RESULT for part in parts):
        return ModelResponse(parts=[TextPart(MODEL_RESULT)])
    if info.function_tools:
        return ModelResponse(parts=[ToolCallPart("fixture_page", {})])
    raise ValueError("The model is missing the registered fixture tool")


agent = Agent(
    FunctionModel(model_reply),
    name="payload_codec_fixture",
    capabilities=[
        TemporalDurability(
            activity_config={
                "start_to_close_timeout": ACTIVITY_TIMEOUT,
                "retry_policy": NO_RETRY,
            },
            model_activity_config={
                "start_to_close_timeout": ACTIVITY_TIMEOUT,
                "retry_policy": NO_RETRY,
            },
        ),
    ],
)


@agent.tool_plain
async def fixture_page() -> str:
    return TOOL_RESULT


@workflow.defn(name="test.codec.ai", sandboxed=False)
class AgentWorkflow(PydanticAIWorkflow):
    @workflow.run
    async def run(self, image: bytes) -> str:
        result = await agent.run([BinaryContent(data=image, media_type="image/png"), "Read page"])
        return result.output


AgentWorkflow.__pydantic_ai_agents__ = [agent]


class ProbeActivities:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.arrivals = 0
        self.all_arrived = asyncio.Event()

    @activity.defn(name="test.codec.recorded")
    async def recorded(self, image: bytes) -> bytes:
        # One marker per actual Activity execution, so replay can be checked independently
        # of the stored Temporal completion event.
        marker = self.root / "recorded-calls"
        with marker.open("a", encoding="utf-8") as output:
            output.write(f"{hashlib.sha256(image).hexdigest()}\n")
        return image

    @activity.defn(name="test.codec.near_limit")
    async def near_limit(self, marker: int) -> bytes:
        self.arrivals += 1
        if self.arrivals == PARALLEL_ACTIVITIES:
            self.all_arrived.set()
        await self.all_arrived.wait()
        return bytes([marker]) * NEAR_LIMIT_BYTES


@workflow.defn(name="test.codec.replay", sandboxed=False)
class ReplayWorkflow:
    def __init__(self) -> None:
        self.released = False

    @workflow.signal
    async def release(self) -> None:
        self.released = True

    @workflow.run
    async def run(self, image: bytes) -> bytes:
        saved = await workflow.execute_activity_method(
            ProbeActivities.recorded,
            image,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY,
        )
        await workflow.wait_condition(lambda: self.released)
        return saved


@workflow.defn(name="test.codec.inline", sandboxed=False)
class InlineWorkflow:
    @workflow.run
    async def run(self, data: bytes) -> bytes:
        return data


@workflow.defn(name="test.codec.memory", sandboxed=False)
class MemoryWorkflow:
    @workflow.run
    async def run(self, marker: int) -> bytes:
        return await workflow.execute_activity_method(
            ProbeActivities.near_limit,
            marker,
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=NO_RETRY,
        )


async def run_worker(database: URL, settings: Settings, ready: Path) -> None:
    engine = application_engine(database)
    methods = ProbeActivities(settings.files_root)
    try:
        client = await connect_temporal(settings, engine)
        async with Worker(
            client,
            task_queue=settings.task_queue,
            workflows=[AgentWorkflow, ReplayWorkflow, InlineWorkflow, MemoryWorkflow],
            activities=[methods.recorded, methods.near_limit],
            max_concurrent_workflow_tasks=2,
            max_concurrent_activities=PARALLEL_ACTIVITIES,
            max_cached_workflows=8,
        ):
            ready.touch()
            await asyncio.Future[None]()
    finally:
        await engine.dispose()


def worker_process(database: URL, settings: Settings, ready: Path) -> None:
    asyncio.run(run_worker(database, settings, ready))
