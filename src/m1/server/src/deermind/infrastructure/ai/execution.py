"""AI步骤的持久接线；候选保存独立于模型Activity，业务提交仍由调用方完成。"""

import asyncio
from collections.abc import Mapping, Sequence
from datetime import timedelta
from uuid import UUID

from deermind.abstractions.ai.calls import AIRejected, CallService
from deermind.abstractions.ai.contracts import CallHandle, CallInput, PromptCallInput
from deermind.abstractions.encoding import canonical_json
from pydantic import BaseModel, JsonValue, TypeAdapter
from pydantic_ai import Agent
from pydantic_ai.messages import UserContent
from pydantic_ai.usage import UsageLimits
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

CALL_INPUT = TypeAdapter(CallInput | PromptCallInput)


class Activities:
    """短步骤只操作持久状态，不把整个Agent循环塞进Activity。"""

    def __init__(self, calls: CallService, schemas: Mapping[str, type[BaseModel]]) -> None:
        self.calls = calls
        self.schemas = schemas

    @activity.defn(name="ai.prepare_call")
    async def prepare(self, body: str) -> str:
        try:
            handle = await self.calls.prepare(CALL_INPUT.validate_json(body))
            if handle.binding.schema_ref.model_dump_json() not in self.schemas:
                raise AIRejected("configuration_unavailable")
            return handle.model_dump_json()
        except (ValueError, PermissionError):
            raise ApplicationError(
                "AI call rejected", type="AIRequestRejected", non_retryable=True
            ) from None

    @activity.defn(name="ai.save_candidate")
    async def save(self, handle_json: str, output_json: str) -> str:
        try:
            handle = CallHandle.model_validate_json(handle_json)
            schema = self.schemas[handle.binding.schema_ref.model_dump_json()]
            candidate = schema.model_validate_json(output_json, strict=True)
            return str(await self.calls.candidate(handle, candidate.model_dump(mode="json")))
        except (ValueError, PermissionError, KeyError):
            raise ApplicationError(
                "AI candidate rejected", type="AIRequestRejected", non_retryable=True
            ) from None

    @activity.defn(name="ai.fail_call")
    async def fail(self, handle_json: str, code: str) -> None:
        await self.calls.fail(CallHandle.model_validate_json(handle_json), code)


async def execute_ai_task(
    agent: Agent[CallHandle, BaseModel],
    incoming: CallInput | PromptCallInput,
    *,
    user_content: Sequence[UserContent] | None = None,
) -> UUID:
    """供Operation Workflow调用；复用已存候选，不重问模型，也不直接保存业务结果。"""
    if not workflow.in_workflow():
        raise ValueError("Durable AI execution requires a Workflow")
    handle_json = await workflow.execute_activity(
        "ai.prepare_call",
        incoming.model_dump_json(),
        result_type=str,
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(maximum_attempts=2),
    )
    handle = CallHandle.model_validate_json(handle_json)
    if handle.candidate_ref is not None:
        return handle.candidate_ref
    seconds = (
        incoming.run.deadline_at - workflow.now()
    ).total_seconds() - handle.budget.finalize_reserve_seconds
    try:
        if seconds <= 0:
            raise AIRejected("budget_exhausted")
        async with asyncio.timeout(seconds):
            result = await agent.run(
                handle.input.prompt if user_content is None else user_content,
                deps=handle,
                usage_limits=UsageLimits(
                    request_limit=handle.budget.max_model_requests,
                    output_tokens_limit=handle.budget.max_total_tokens,
                ),
            )
            body = TypeAdapter(dict[str, JsonValue]).validate_python(
                result.output.model_dump(mode="json")
            )
            identity = await workflow.execute_activity(
                "ai.save_candidate",
                args=[handle_json, canonical_json(body)],
                result_type=str,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            return UUID(identity)
    except (Exception, asyncio.CancelledError) as error:
        # 只保存固定分类，不把供应商错误、用户正文或认证信息写进失败历史。
        await asyncio.shield(
            workflow.execute_activity(
                "ai.fail_call",
                args=[handle_json, "ai_step_failed_" + type(error).__name__],
                start_to_close_timeout=timedelta(seconds=handle.budget.finalize_reserve_seconds),
                schedule_to_close_timeout=timedelta(seconds=handle.budget.finalize_reserve_seconds),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        )
        raise ApplicationError(
            "AI step did not complete",
            type="AIExecutionFailed/" + type(error).__name__,
            non_retryable=True,
        ) from None
