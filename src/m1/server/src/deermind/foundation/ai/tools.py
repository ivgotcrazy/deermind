"""工具登记、当前权限和调用留痕；正式业务写入仍由工具所有者处理。"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from deermind.abstractions.ai.calls import AIRejected
from deermind.abstractions.ai.contracts import CallHandle
from deermind.abstractions.ai.tools import ToolDescription, ToolResult
from deermind.abstractions.events import Ref
from deermind.abstractions.hashing import digest
from deermind.foundation.ai import store
from deermind.foundation.ai.execution import Calls
from deermind.foundation.ai.records import ToolActionFact
from deermind.foundation.system.executions import store as executions
from pydantic import BaseModel, JsonValue, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Tool:
    """只由程序登记；写草稿工具使用稳定work_key，并自行核验当前业务位置。"""

    reference: Ref
    name: str
    description: str
    parameters: type[BaseModel]
    effect: Literal["read", "draft_write"]
    timeout_seconds: int
    check: Callable[[AsyncConnection, CallHandle, BaseModel], Awaitable[bool]]
    invoke: Callable[[CallHandle, BaseModel, str | None], Awaitable[ToolResult]]


class Tools:
    def __init__(self, calls: Calls, tools: Sequence[Tool]) -> None:
        self.calls = calls
        self.tools = {tool.name: tool for tool in tools}
        if len(self.tools) != len(tools) or any(tool.timeout_seconds <= 0 for tool in tools):
            raise ValueError("Tools require unique names and finite deadlines")

    def descriptions(self) -> tuple[ToolDescription, ...]:
        """只返回工具公开描述；事务校验和调用函数不交给SDK。"""
        return tuple(
            ToolDescription(t.reference, t.name, t.description, t.parameters)
            for t in self.tools.values()
        )

    async def invoke(
        self,
        handle: CallHandle,
        name: str,
        parameters: dict[str, JsonValue],
        turn: int,
        ordinal: int,
    ) -> ToolResult:
        """模型给参数，程序给身份和权限；重试复用收据，不重复写业务草稿。"""
        if turn < 1 or ordinal < 1:
            raise AIRejected("invalid_tool_position")
        action_key = f"{handle.call_id}/{handle.attempt_id}/{turn}/{ordinal}"
        source = Ref(owner="ai", type="execution", id=str(handle.input.run.execution_id))
        reference = await self.calls.attachments.save_json(
            parameters,
            actor=source,
            source=source,
            artifact_key=f"ai-tool-input:{action_key}:{digest(parameters)}",
            max_bytes=handle.budget.max_input_bytes,
        )
        tool = self.tools.get(name)
        parsed: BaseModel | None = None
        if tool is not None:
            try:
                parsed = tool.parameters.model_validate(parameters, strict=True)
            except ValidationError:
                pass
        async with self.calls.engine.begin() as connection:
            call = await self.calls.guard(connection, handle)
            if call.state != "running":
                raise AIRejected("call_not_running")
            execution = await executions.load(connection, handle.input.run.execution_id)
            saved = await store.load(
                connection,
                "ai.tool_actions",
                ToolActionFact,
                {"tool_action_key": action_key, "attempt_id": handle.attempt_id},
            )
            if saved is not None and (saved.parameters_ref != reference or saved.tool_name != name):
                raise AIRejected("input_conflict")
            allowed = (
                tool is not None
                and tool.reference in handle.binding.tool_refs
                and tool.reference in handle.input.tool_grants
            )
            if allowed and parsed is not None and tool is not None:
                allowed = await tool.check(connection, handle, parsed)
            if saved is None or saved.outcome == "pending":
                count = await connection.scalar(
                    text(
                        "SELECT tool_count FROM ai.execution_usage "
                        "WHERE execution_id=:id FOR UPDATE"
                    ),
                    {"id": execution.execution_id},
                )
                if count >= handle.budget.max_tool_attempts:
                    raise AIRejected("budget_exhausted")
                await connection.execute(
                    text(
                        "UPDATE ai.execution_usage SET tool_count=tool_count+1,"
                        "updated_at=clock_timestamp() WHERE execution_id=:id"
                    ),
                    {"id": execution.execution_id},
                )
            if saved is None:
                timestamp = await store.now(connection)
                work_key = (
                    f"{handle.call_id}/tool/{turn}/{ordinal}"
                    if tool and tool.effect == "draft_write"
                    else None
                )
                saved = ToolActionFact(
                    tool_action_key=action_key,
                    attempt_id=handle.attempt_id,
                    call_id=handle.call_id,
                    tool_name=name,
                    parameters_ref=reference,
                    result_ref=None,
                    authorization_result="allowed" if allowed else "denied",
                    work_key=work_key,
                    owner_receipt_ref=None,
                    outcome="pending" if allowed else "denied",
                    started_at=timestamp,
                    finished_at=None if allowed else timestamp,
                )
                await store.record(
                    connection,
                    execution,
                    "ToolActionChanged",
                    "started" if allowed else "denied",
                    [("ai.tool_actions", saved)],
                    reason=None if allowed else "forbidden",
                )
        if not allowed or tool is None:
            raise AIRejected("forbidden")
        if saved.outcome == "completed" and saved.result_ref is not None:
            body = await self.calls.attachments.read_json(
                saved.result_ref, source=source, max_bytes=handle.budget.max_result_bytes
            )
            return ToolResult.model_validate(body)
        if saved.outcome != "pending":
            raise AIRejected("tool_already_failed")
        error: str | None = None
        result_ref: Ref | None = None
        result: ToolResult | None = None
        try:
            if parsed is None:
                result = ToolResult(
                    status="invalid_arguments", data={}, source_refs=[], owner_receipt_ref=None
                )
            else:
                remaining = await self.calls.remaining(handle)
                async with asyncio.timeout(min(tool.timeout_seconds, remaining)):
                    result = await tool.invoke(handle, parsed, saved.work_key)
            result_ref = await self.calls.attachments.save_json(
                result.model_dump(mode="json"),
                actor=source,
                source=source,
                artifact_key=f"ai-tool-result:{action_key}",
                max_bytes=handle.budget.max_result_bytes,
            )
        except (Exception, asyncio.CancelledError):
            error = "tool_failed"
        async with self.calls.engine.begin() as connection:
            execution = await executions.lock_owned(
                connection, self.calls.registry, handle.input.run.execution_id
            )
            finished = saved.model_copy(
                update={
                    "result_ref": result_ref,
                    "owner_receipt_ref": result.owner_receipt_ref if result else None,
                    "outcome": "failed" if error else "completed",
                    "finished_at": await store.now(connection),
                }
            )
            await store.record(
                connection,
                execution,
                "ToolActionChanged",
                "failed" if error else "completed",
                [("ai.tool_actions", finished)],
                reason=error,
            )
        if error or result is None:
            raise AIRejected("tool_failed")
        return result
