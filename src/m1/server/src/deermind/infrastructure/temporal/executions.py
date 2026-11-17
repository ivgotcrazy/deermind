"""Temporal执行适配；不编排业务步骤，不用Workflow历史代替业务收据。"""

from datetime import UTC, datetime, timedelta

from deermind.abstractions.events import Ref
from deermind.abstractions.executions import (
    Dispatch,
    ExecutionNotFound,
    LifecycleService,
    Limits,
    RunInput,
)
from temporalio import activity
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode


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

    async def _cancel(self, command: Dispatch) -> None:
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

    async def running(self, command: Dispatch) -> bool:
        try:
            description = await self.client.get_workflow_handle(command.workflow_id).describe(
                rpc_timeout=timedelta(seconds=self.limits.request_seconds)
            )
        except RPCError as error:
            if error.status == RPCStatusCode.NOT_FOUND:
                raise ExecutionNotFound(command.workflow_id) from None
            raise
        if (
            await description.memo_value("deermind_input", type_hint=str)
            != command.run.model_dump_json()
        ):
            raise ValueError("Workflow input differs from the saved work")
        return description.status == WorkflowExecutionStatus.RUNNING

    async def cancel(self, command: Dispatch) -> None:
        try:
            await self._cancel(command)
        except RPCError as error:
            if error.status == RPCStatusCode.NOT_FOUND:
                raise ExecutionNotFound(command.workflow_id) from None
            raise


class Lifecycle:
    """SDK外壳只解析输入及转换错误；不打开数据库事务。"""

    def __init__(self, service: LifecycleService) -> None:
        self.service = service

    @activity.defn(name="runtime.execution_started")
    async def started(self, body: str) -> None:
        run = RunInput.model_validate_json(body)
        try:
            await self.service.started(run)
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
            await self.service.completed(run, Ref.model_validate_json(result))
        except (ValueError, PermissionError) as error:
            raise ApplicationError(
                "Execution state or authorization rejected",
                type=type(error).__name__,
                non_retryable=True,
            ) from None

    @activity.defn(name="runtime.execution_failed")
    async def failed(self, body: str, error_code: str) -> None:
        await self.service.failed(RunInput.model_validate_json(body), error_code)
