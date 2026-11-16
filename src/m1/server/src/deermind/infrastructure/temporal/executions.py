"""Temporal执行适配；不编排业务步骤，不用Workflow历史代替业务收据。"""

import asyncio
from datetime import UTC, datetime, timedelta

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.executions import commands
from deermind.foundation.system.executions.contracts import Dispatch, Limits, Registry, RunInput
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError


class Transport:
    """稳定ID启动；响应丢失查同一ID及固定输入，绝不换ID再开一份。"""

    def __init__(self, client: Client, limits: Limits) -> None:
        self.client = client
        self.limits = limits

    async def start(self, command: Dispatch) -> str:
        remaining = (command.run.deadline_at - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            raise ValueError("Execution deadline expired before dispatch")
        body = command.run.model_dump_json()
        try:
            handle = await self.client.start_workflow(
                command.workflow_type,
                body,
                id=command.workflow_id,
                task_queue=command.task_queue,
                execution_timeout=timedelta(seconds=remaining),
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
                memo={"deermind_input": body},
                rpc_timeout=timedelta(seconds=self.limits.request_seconds),
            )
            assert handle.first_execution_run_id is not None
            return handle.first_execution_run_id
        except WorkflowAlreadyStartedError:
            description = await self.client.get_workflow_handle(command.workflow_id).describe(
                rpc_timeout=timedelta(seconds=self.limits.request_seconds)
            )
            if await description.memo_value("deermind_input", type_hint=str) != body:
                raise ValueError("Workflow identity has different saved input") from None
            return description.run_id

    async def signal(self, command: Dispatch) -> None:
        """只通知已经存在的指定执行；未知ID按交接失败重试，绝不顺手启动。"""
        if command.wait_id is None:
            raise ValueError("Signal must identify its wait")
        handle = self.client.get_workflow_handle(command.workflow_id)
        description = await handle.describe(
            rpc_timeout=timedelta(seconds=self.limits.request_seconds)
        )
        if (
            await description.memo_value("deermind_input", type_hint=str)
            != command.run.model_dump_json()
        ):
            raise ValueError("Signal input differs from the original work")
        if description.status == WorkflowExecutionStatus.RUNNING:
            await self.client.get_workflow_handle(
                command.workflow_id, run_id=description.run_id
            ).signal(
                "runtime.wait_changed",
                str(command.wait_id),
                rpc_timeout=timedelta(seconds=self.limits.request_seconds),
            )

    async def cancel(self, command: Dispatch) -> None:
        handle = self.client.get_workflow_handle(command.workflow_id)
        description = await handle.describe(
            rpc_timeout=timedelta(seconds=self.limits.request_seconds)
        )
        if (
            await description.memo_value("deermind_input", type_hint=str)
            != command.run.model_dump_json()
        ):
            raise ValueError("Cancellation input does not match the original work")
        if description.status == WorkflowExecutionStatus.RUNNING:
            await self.client.get_workflow_handle(
                command.workflow_id, run_id=description.run_id
            ).cancel(rpc_timeout=timedelta(seconds=self.limits.request_seconds))


class Lifecycle:
    """供业务Workflow使用的公共Activity；业务步骤仍由所属模块组织。"""

    def __init__(self, engine: AsyncEngine, registry: Registry, limits: Limits) -> None:
        self.engine = engine
        self.registry = registry
        self.limits = limits

    @activity.defn(name="runtime.execution_started")
    async def started(self, body: str) -> None:
        run = RunInput.model_validate_json(body)
        try:
            async with self.engine.begin() as connection:
                await commands.start(connection, self.registry, run)
        except (ValueError, PermissionError) as error:
            raise ApplicationError(
                "Execution state or authorization rejected",
                type=type(error).__name__,
                non_retryable=True,
            ) from None

    @activity.defn(name="runtime.execution_completed")
    async def completed(self, body: str, result: str) -> None:
        run = RunInput.model_validate_json(body)
        try:
            async with (
                asyncio.timeout(self.limits.finalize_seconds),
                self.engine.begin() as connection,
            ):
                await commands.complete(
                    connection, self.registry, run, Ref.model_validate_json(result)
                )
        except (ValueError, PermissionError) as error:
            raise ApplicationError(
                "Execution state or authorization rejected",
                type=type(error).__name__,
                non_retryable=True,
            ) from None

    @activity.defn(name="runtime.execution_failed")
    async def failed(self, body: str, error_code: str) -> None:
        run = RunInput.model_validate_json(body)
        # 只记录固定错误码及执行定位，不复制可能包含正文/凭据的异常消息。
        failure = Ref(
            owner="runtime", type="execution_failure", id=str(run.attempt_id), path=error_code
        )
        async with asyncio.timeout(self.limits.finalize_seconds), self.engine.begin() as connection:
            await commands.fail(connection, self.registry, run, failure)
