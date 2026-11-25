"""Pydantic AI模型适配；只在Activity外发，密钥不进入deps、事实或Temporal历史。"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AsyncExitStack
from dataclasses import replace
from typing import Any

import httpx2
from deermind.abstractions.ai.calls import AIRejected, CallService
from deermind.abstractions.ai.contracts import CallHandle, ModelProfile
from deermind.abstractions.encoding import canonical_json
from deermind.abstractions.events import Ref
from deermind.abstractions.hashing import digest
from openai import AsyncOpenAI
from pydantic import JsonValue, TypeAdapter
from pydantic_ai.messages import (
    BinaryContent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    RetryFeedbackPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
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
        calls: CallService,
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
            # 模型请求必须在 Activity 内发出，Workflow 内不得直连供应商。
            raise AIRejected("model_io_requires_activity")
        handle = self.handle
        await self.calls.remaining(handle)
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
            # 固定编码后的请求体超出输入字节预算，不发起请求。
            raise AIRejected("required_context_too_large")
        # 图片原始字节仍计入传输大小。DeepSeek 每张图片最多 1024 tokens。
        estimate = bounded_tokens(body, messages, handle.binding.profile)
        ordinal = sum(isinstance(item, ModelResponse) for item in messages) + 1
        transport = activity.info().attempt if activity.in_activity() else 1
        # 首次传输且上一请求带重试反馈/工具重试回执，才计入 repair 用量。
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
        request_ref = await self.calls.save_material(
            body,
            actor=source,
            source=source,
            artifact_key=f"ai-request:{handle.call_id}:{handle.attempt_id}:{ordinal}:{transport}:{digest(body)}",
            max_bytes=handle.budget.max_input_bytes,
        )
        saved = await self.calls.reserve(
            handle, ordinal, transport, request_ref, estimate, repair=repair
        )
        if saved.outcome == "success" and saved.response_ref is not None:
            # 已有确认的保存响应，直接复用，不再重问模型。
            previous = await self.calls.read_material(
                saved.response_ref, source=source, max_bytes=handle.budget.max_result_bytes
            )
            return checked_response(
                TypeAdapter(ModelResponse).validate_python(previous), model_request_parameters
            )
        if saved.outcome != "pending":
            # 预约结果为失败/取消等终态，本次请求不再继续。
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
                # 凭据缺失，禁止回退旧密钥或换用其他模型。
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
                    # 本层创建的 OpenAI 客户端需随请求一并关闭。
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
            response_ref = await self.calls.save_material(
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
            # 被取消也要在后台落账，避免会话持锁后用量悬空。
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
            # 非取消异常先落账，再按错误类别决定是否可重试。
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
            # 业务拒绝/参数错误，或 4xx（除 429 限流）判定为永久失败，不可重试。
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


def bounded_tokens(
    body: dict[str, JsonValue], messages: list[ModelMessage], profile: ModelProfile
) -> int:
    """分开估算文字与内联图片；真实计费仍依据服务商响应。"""
    text_messages: list[ModelMessage] = []
    images = 0
    for message in messages:
        if not isinstance(message, ModelRequest):
            # 非请求消息直接参与文本编码估算。
            text_messages.append(message)
            continue
        parts: list[ModelRequestPart] = []
        for part in message.parts:
            if isinstance(part, UserPromptPart) and not isinstance(part.content, str):
                contents: list[str] = []
                for item in part.content:
                    if isinstance(item, str):
                        contents.append(item)
                    elif (
                        isinstance(item, BinaryContent)
                        and item.media_type in {"image/jpeg", "image/png"}
                        and profile.base_url.rstrip("/") == "https://api.deepseek.com"
                    ):
                        # 受信供应商支持的图片，以占位符计入文本并单独估算图片 tokens。
                        contents.append("[image]")
                        images += 1
                    else:
                        # 其余二进制内容当前输入合同不支持。
                        raise AIRejected("unsupported_input")
                part = replace(part, content=contents)
            parts.append(part)
        text_messages.append(replace(message, parts=parts))
    encoded_text = ModelMessagesTypeAdapter.dump_python(text_messages, mode="json")
    return len(canonical_body({**body, "messages": encoded_text})) + 256 + 1024 * images


def checked_response(response: ModelResponse, parameters: ModelRequestParameters) -> ModelResponse:
    """新响应与已存响应执行相同检查，缓存不扩大工具权限。"""
    calls = [part for part in response.parts if isinstance(part, ToolCallPart)]
    if len({part.tool_call_id for part in calls}) != len(calls):
        # 工具调用编号重复，无法唯一定位回执。
        raise AIRejected("duplicate_tool_identity")
    permitted = {tool.name for tool in parameters.function_tools + parameters.output_tools}
    if any(part.tool_name not in permitted for part in calls):
        # 模型调用了未授权工具，缓存响应同样不得放行。
        raise AIRejected("forbidden_tool")
    return response


def canonical_body(value: dict[str, JsonValue]) -> bytes:
    """模型请求的固定编码，大小检查与保存使用同一表示。"""
    return canonical_json(value).encode("utf-8")
