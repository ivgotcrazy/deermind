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
            # 已过运行截止时间，不再启动新执行。
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
            # 同一稳定 ID 已有执行，核对其保存输入而非另开一份。
            description = await self.client.get_workflow_handle(command.workflow_id).describe(
                rpc_timeout=timedelta(seconds=self.limits.request_seconds)
            )
            if await description.memo_value("deermind_input", type_hint=str) != body:
                # 同名 ID 对应不同输入，判定身份冲突。
                raise ValueError("Workflow identity has different saved input") from None
            return description.run_id

    async def signal(self, command: Dispatch) -> None:
        """只通知已经存在的指定执行；未知ID按交接失败重试，绝不顺手启动。"""
        if command.wait_id is None:
            # 信号必须指向具体等待项，无法定位则拒绝投递。
            raise ValueError("Signal must identify its wait")
        handle = self.client.get_workflow_handle(command.workflow_id)
        description = await handle.describe(
            rpc_timeout=timedelta(seconds=self.limits.request_seconds)
        )
        if (
            await description.memo_value("deermind_input", type_hint=str)
            != command.run.model_dump_json()
        ):
            # 信号输入与原执行保存输入不一致，防止串到同名旧执行。
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
            # 取消前同样核对输入，避免误停同名执行。
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
                # 执行不存在，转为业务层可识别的未找到错误。
                raise ExecutionNotFound(command.workflow_id) from None
            raise
        if (
            await description.memo_value("deermind_input", type_hint=str)
            != command.run.model_dump_json()
        ):
            # 描述到的执行输入与当前工作不符，判定身份不一致。
            raise ValueError("Workflow input differs from the saved work")
        return description.status == WorkflowExecutionStatus.RUNNING

    async def cancel(self, command: Dispatch) -> None:
        try:
            await self._cancel(command)
        except RPCError as error:
            if error.status == RPCStatusCode.NOT_FOUND:
                # 取消时执行已不存在，按未找到向上传递。
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
            # 状态校验或授权拒绝转为不可重试的业务错误。
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
            # 状态校验或授权拒绝转为不可重试的业务错误。
            raise ApplicationError(
                "Execution state or authorization rejected",
                type=type(error).__name__,
                non_retryable=True,
            ) from None

    @activity.defn(name="runtime.execution_failed")
    async def failed(self, body: str, error_code: str) -> None:
        await self.service.failed(RunInput.model_validate_json(body), error_code)
