"""Pydantic AI模型适配；只在Activity外发，密钥不进入deps、事实或Temporal历史。"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import replace
from typing import Any

import httpx2
from deermind.foundation.ai import store
from deermind.foundation.ai.contracts import CallHandle, ModelProfile
from deermind.foundation.ai.execution import AIRejected, Calls
from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.events.store import canonical_json
from openai import AsyncOpenAI
from pydantic import JsonValue, TypeAdapter
from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    RetryFeedbackPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.profiles import ModelProfile as SDKProfile
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError

# Any仅对应SDK的多种供应商客户端类型；业务输入与保存正文均先按固定Schema校验。
ModelFactory = Callable[[ModelProfile, str], Model[Any]]
SecretReader = Callable[[str], str]
LOGGER = logging.getLogger("ai")


def provider_model(profile: ModelProfile, key: str) -> Model[Any]:
    """SDK不自行重试；连接10秒、请求90秒，上层还会收紧到工作剩余时间。"""
    client = AsyncOpenAI(
        api_key=key,
        base_url=profile.base_url,
        max_retries=0,
        timeout=httpx2.Timeout(90.0, connect=10.0),
    )
    return OpenAIChatModel(profile.model, provider=OpenAIProvider(openai_client=client))


class ControlledModel(Model[None]):
    """解析阶段无I/O；真正请求时校验权限、预约用量，再创建当前凭据对应的客户端。"""

    def __init__(
        self,
        handle: CallHandle,
        calls: Calls,
        credentials: SecretReader,
        *,
        factory: ModelFactory = provider_model,
    ) -> None:
        super().__init__(profile=SDKProfile(supports_tools=True, supports_json_schema_output=False))
        self.handle, self.calls, self.credentials, self.factory = (
            handle,
            calls,
            credentials,
            factory,
        )

    @property
    def model_name(self) -> str:
        return self.handle.binding.profile.model

    @property
    def system(self) -> str:
        return "openai"

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """每次真实传输单独记录；已保存响应可复用，已发未确认保留未知用量。"""
        if workflow.in_workflow():
            raise AIRejected("model_io_requires_activity")
        handle = self.handle
        await self.calls.remaining(handle)
        # 此增量只接短文字；多模态装载与大历史外置在E01-16接入。
        encoded_messages = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
        parameters = TypeAdapter(ModelRequestParameters).dump_python(
            model_request_parameters, mode="json"
        )
        body = TypeAdapter(dict[str, JsonValue]).validate_python(
            {
                "messages": encoded_messages,
                "parameters": parameters,
                "model": self.model_name,
                "thinking": "disabled",
                "temperature": 0,
                "max_tokens": handle.budget.max_output_tokens,
            }
        )
        encoded = canonical_body(body)
        if len(encoded) > handle.budget.max_input_bytes:
            raise AIRejected("required_context_too_large")
        # 保守预约UTF-8字节数并留消息框架余量，不冒充供应商精确tokenizer或实际计费。
        estimate = len(encoded) + 256
        ordinal = sum(isinstance(item, ModelResponse) for item in messages) + 1
        transport = activity.info().attempt if activity.in_activity() else 1
        repair = (
            transport == 1
            and bool(messages)
            and isinstance(messages[-1], ModelRequest)
            and any(
                isinstance(part, RetryFeedbackPart)
                or (isinstance(part, ToolReturnPart) and part.outcome == "retried")
                for part in messages[-1].parts
            )
        )
        source = Ref(owner="ai", type="execution", id=str(handle.input.run.execution_id))
        request_ref = await self.calls.attachments.save_json(
            body,
            actor=source,
            source=source,
            artifact_key=f"ai-request:{handle.call_id}:{handle.attempt_id}:{ordinal}:{transport}:{store.digest(body)}",
            max_bytes=handle.budget.max_input_bytes,
        )
        saved = await self.calls.reserve(
            handle, ordinal, transport, request_ref, estimate, repair=repair
        )
        if saved.outcome == "success" and saved.response_ref is not None:
            previous = await self.calls.attachments.read_json(
                saved.response_ref, source=source, max_bytes=handle.budget.max_result_bytes
            )
            return checked_response(
                TypeAdapter(ModelResponse).validate_python(previous), model_request_parameters
            )
        if saved.outcome != "pending":
            raise AIRejected("request_already_failed")

        context = {
            "execution_id": str(handle.input.run.execution_id),
            "request_id": f"{handle.call_id}/{handle.attempt_id}/{ordinal}/{transport}",
        }
        LOGGER.info(
            "开始模型请求", extra={**context, "action": "model_request", "outcome": "pending"}
        )

        response: ModelResponse | None = None
        try:
            # 读取当前凭据在预约之后；失败仍留痕，不能回退至旧密钥或另一模型。
            key = self.credentials(handle.binding.profile.credential_ref)
            if not key:
                raise AIRejected("configuration_unavailable")
            model = self.factory(handle.binding.profile, key)
            remaining = await self.calls.remaining(handle)
            settings: ModelSettings = {
                "max_tokens": handle.budget.max_output_tokens,
                "temperature": 0,
                "parallel_tool_calls": False,
                "timeout": min(90.0, remaining),
                "extra_body": {"thinking": {"type": "disabled"}},
            }
            async with asyncio.timeout(min(90.0, remaining)), AsyncExitStack() as stack:
                # 注入OpenAI客户端由本层创建；Provider不负责关闭外部传入的客户端。
                if isinstance(model, OpenAIChatModel):
                    await stack.enter_async_context(model.client)
                await stack.enter_async_context(model)
                response = await model.request(messages, settings, model_request_parameters)
            # thinking关闭仍不保存供应商意外带回的隐藏思考。
            response = replace(
                response,
                parts=[part for part in response.parts if not isinstance(part, ThinkingPart)],
            )
            content = TypeAdapter(dict[str, JsonValue]).validate_python(
                TypeAdapter(ModelResponse).dump_python(response, mode="json")
            )
            response_ref = await self.calls.attachments.save_json(
                content,
                actor=source,
                source=source,
                artifact_key=f"ai-response:{handle.call_id}:{handle.attempt_id}:{ordinal}:{transport}",
                max_bytes=handle.budget.max_result_bytes,
            )
            usage = response.usage
            actual = (
                (usage.input_tokens, usage.output_tokens)
                if usage.input_tokens + usage.output_tokens > 0
                else None
            )
            await self.calls.settle(
                handle,
                saved,
                response_ref=response_ref,
                actual_usage=actual,
                provider_id=response.provider_response_id,
                error_code=None,
            )
            LOGGER.info(
                "模型响应已保存", extra={**context, "action": "model_request", "outcome": "success"}
            )
        except asyncio.CancelledError:
            await asyncio.shield(
                self.calls.settle(
                    handle,
                    saved,
                    response_ref=None,
                    actual_usage=None,
                    provider_id=None,
                    error_code="cancelled",
                )
            )
            raise
        except Exception as error:
            code = str(error) if isinstance(error, AIRejected) else "model_request_failed"
            LOGGER.warning(
                "模型请求未完成",
                extra={
                    **context,
                    "action": "model_request",
                    "outcome": "failed",
                    "error_code": code,
                },
            )
            await self.calls.settle(
                handle,
                saved,
                response_ref=None,
                actual_usage=None,
                provider_id=None,
                error_code=code,
            )
            # SDK异常可能含响应正文和请求地址；Temporal只收固定分类。
            status = getattr(error, "status_code", None)
            permanent = isinstance(error, (AIRejected, ValueError)) or (
                isinstance(status, int) and status < 500 and status != 429
            )
            raise ApplicationError(
                code,
                type="AIRequestRejected" if permanent else "AITransportFailure",
                non_retryable=permanent,
            ) from None
        assert response is not None
        return checked_response(response, model_request_parameters)


def checked_response(response: ModelResponse, parameters: ModelRequestParameters) -> ModelResponse:
    """新响应与已存响应执行相同检查，缓存不扩大工具权限。"""
    calls = [part for part in response.parts if isinstance(part, ToolCallPart)]
    if len({part.tool_call_id for part in calls}) != len(calls):
        raise AIRejected("duplicate_tool_identity")
    permitted = {tool.name for tool in parameters.function_tools + parameters.output_tools}
    if any(part.tool_name not in permitted for part in calls):
        raise AIRejected("forbidden_tool")
    return response


def canonical_body(value: dict[str, JsonValue]) -> bytes:
    """模型请求的固定编码，大小检查与保存使用同一表示。"""
    return canonical_json(value).encode("utf-8")
