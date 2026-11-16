"""E01-15合成工作与模型替身；不注册为正式业务Operation，不访问真实教材。"""

from typing import ClassVar
from uuid import uuid4

from deermind.foundation.ai import store as ai_store
from deermind.foundation.ai.contracts import (
    Budget,
    CallHandle,
    CallInput,
    ExecutionConfig,
    ModelProfile,
    PurposeBinding,
)
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.tools import Tool, ToolResult, Tools
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.contracts import FactModel, Ref
from deermind.foundation.system.executions import commands, store
from deermind.foundation.system.executions.contracts import (
    Authorization,
    Caller,
    Entry,
    Execution,
    Registry,
    RunInput,
    State,
)
from deermind.infrastructure.ai.agent import Purpose
from deermind.infrastructure.ai.execution import execute_ai_task
from deermind.infrastructure.files.local import LocalFiles
from execution_worker import lock_owner
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.durable_exec.temporal import PydanticAIWorkflow
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from temporalio import workflow


class Output(FactModel):
    answer: str


class Arguments(FactModel):
    query: str


class Fixture:
    def __init__(self, engine: AsyncEngine, files: LocalFiles, queue: str) -> None:
        self.scope = uuid4()
        self.queue = queue
        self.allowed = True
        self.tool_effects = 0
        self.registry = Registry(
            [
                Entry(
                    "interaction",
                    "interaction.ai_test",
                    "ai_operation",
                    Ref(owner="interaction", type="implementation", id="ai-test", revision=1),
                    "test.ai",
                    queue,
                    lock_owner,
                    self.check,
                    self.finalize,
                )
            ]
        )
        self.reference = Ref(owner="interaction", type="purpose", id="ai-test", revision=1)
        self.purpose = Purpose("ai_test", self.reference, self.reference, self.reference, Output)
        self.tool_ref = Ref(owner="interaction", type="tool", id="lookup", revision=1)
        self.config = ExecutionConfig(
            revision="fixture-v1",
            purpose_bindings={
                "ai_test": PurposeBinding(
                    contract_ref=self.reference,
                    prompt_ref=self.reference,
                    schema_ref=self.reference,
                    tool_refs=[self.tool_ref],
                    profile=ModelProfile(
                        connection_ref=self.reference,
                        profile_ref=self.reference,
                        adapter="openai_chat",
                        base_url="https://example.invalid/v1",
                        credential_ref="fixture-key",
                        model="fixture-model",
                        thinking="disabled",
                        temperature=0,
                    ),
                )
            },
            # 本地替身限额，不用于真实模型测试或正式用途。
            budget=Budget(
                max_model_requests=4,
                max_tool_attempts=3,
                max_repairs=1,
                max_input_tokens=16384,
                max_output_tokens=512,
                max_total_tokens=67584,
                max_input_bytes=32768,
                max_result_bytes=32768,
                finalize_reserve_seconds=10,
            ),
        )
        self.calls = Calls(engine, self.registry, FactAttachments(engine, files))
        self.tools = Tools(
            self.calls,
            [
                Tool(
                    self.tool_ref,
                    "lookup",
                    "Read the supplied fixture value",
                    Arguments,
                    "read",
                    10,
                    self.check_tool,
                    self.invoke_tool,
                )
            ],
        )

    async def check(
        self,
        connection: AsyncConnection,
        execution: Execution,
        authorization: Authorization,
        action: str,
    ) -> None:
        if not self.allowed or execution.scope_id != self.scope:
            raise PermissionError("Fixture authorization revoked")

    async def finalize(
        self, connection: AsyncConnection, execution: Execution, state: State, result: Ref | None
    ) -> None:
        """合成工作没有额外业务表；只核对公共执行和AI记录。"""

    async def check_tool(
        self, connection: AsyncConnection, handle: object, parameters: BaseModel
    ) -> bool:
        return self.allowed

    async def invoke_tool(
        self, handle: object, parameters: BaseModel, key: str | None
    ) -> ToolResult:
        self.tool_effects += 1
        return ToolResult(
            status="ok",
            data={"value": "five quarters"},
            source_refs=[self.reference],
            owner_receipt_ref=None,
        )

    def caller(self) -> Caller:
        return Caller(
            self.reference,
            "interaction",
            frozenset({("learning_space", self.scope)}),
            frozenset({"accept", "read", "retry", "cancel"}),
        )

    async def accept(self, connection: AsyncConnection, key: str) -> CallInput:
        execution = await store.accept(
            connection,
            self.registry,
            self.caller(),
            entry_name="interaction.ai_test",
            scope_kind="learning_space",
            scope_id=self.scope,
            acceptance_key=key,
            input_ref=self.reference,
            seconds=300,
            basis_refs=[self.reference],
            ai_config_ref=uuid4(),
        )
        await ai_store.pin(connection, execution, self.config)
        assert execution.active_attempt_id is not None
        attempt = await store.attempt(connection, execution.active_attempt_id)
        run = RunInput(
            execution_id=execution.execution_id,
            attempt_id=attempt.attempt_id,
            input_ref=execution.input_ref,
            implementation_ref=execution.implementation_ref,
            ai_config_ref=execution.ai_config_ref,
            deadline_at=attempt.deadline_at,
        )
        await commands.start(connection, self.registry, run)
        return CallInput(
            run=run,
            step_key="answer",
            call_key="primary",
            purpose="ai_test",
            instructions="Return the requested answer using the output tool.",
            prompt="What is one plus one quarter?",
            material_refs=[],
            tool_grants=[self.tool_ref],
        )


@workflow.defn(name="test.ai", sandboxed=False)
class AIWorkflow(PydanticAIWorkflow):
    """测试注册共享Agent；真正业务流程仍留所属增量实现。"""

    agent: ClassVar[
        Agent[CallHandle, BaseModel]
    ]  # SDK注册支持不同输出类型，测试在Worker启动前固定。

    @workflow.run
    async def run(self, body: str) -> str:
        candidate = await execute_ai_task(self.agent, CallInput.model_validate_json(body))
        return str(candidate)
