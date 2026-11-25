"""等待只占Temporal历史；探测与接续在短Activity中运行，不占长连接。"""

import logging
from datetime import timedelta
from uuid import UUID

from deermind.abstractions.waits import Handling, Wait, WaitCall, WaitService
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

LOGGER = logging.getLogger("runtime")


class Activities:
    """等待Activity只做协议转换；底座服务负责同事务探测和接续。"""

    def __init__(self, service: WaitService) -> None:
        self.service = service

    @activity.defn(name="runtime.wait_probe")
    async def probe(self, body: str) -> str:
        call = WaitCall.model_validate_json(body)
        try:
            return (await self.service.probe(call)).model_dump_json()
        except (ValueError, PermissionError) as error:
            # 探测输入非法或无权限，转为不可重试错误。
            raise ApplicationError(
                "Wait probe rejected", type=type(error).__name__, non_retryable=True
            ) from None

    @activity.defn(name="runtime.wait_handle")
    async def handle(self, body: str) -> str:
        call = WaitCall.model_validate_json(body)
        try:
            return (await self.service.handle(call)).model_dump_json()
        except (ValueError, PermissionError) as error:
            # 接续输入非法或无权限，转为不可重试错误。
            raise ApplicationError(
                "Wait handling rejected", type=type(error).__name__, non_retryable=True
            ) from None


class WaitSignals:
    """业务Workflow的signal函数转交receive；早到提示先保存，重复提示合并。"""

    def __init__(self) -> None:
        self.pending: set[str] = set()

    def receive(self, identity: str) -> None:
        self.pending.add(str(UUID(identity)))

    async def resume(
        self, call: WaitCall, *, activity_timeout: timedelta, retry_policy: RetryPolicy
    ) -> Handling:
        """先补查再挂起；Timer到期仍补查一次。Activity预算由所属工作给出。"""
        identity = str(call.wait_id)
        # 循环探测：每次先清掉早到提示，再补查等待是否已解决。
        while True:
            self.pending.discard(identity)
            remaining = call.run.deadline_at - workflow.now()
            if remaining.total_seconds() <= 0:
                # 已过执行截止时间，不再等待接续。
                raise ApplicationError("Execution deadline expired", non_retryable=True)
            body = await workflow.execute_activity(
                "runtime.wait_probe",
                call.model_dump_json(),
                result_type=str,
                start_to_close_timeout=min(activity_timeout, remaining),
                schedule_to_close_timeout=remaining,
                retry_policy=retry_policy,
            )
            saved = Wait.model_validate_json(body)
            if saved.resolution != "pending":
                # 等待已有结论，退出探测循环进入接续。
                break
            remaining = saved.deadline_at - workflow.now()
            if remaining.total_seconds() > 0:
                try:
                    # 挂起等待早到提示或等待时限，超时后回到下一轮补查。
                    await workflow.wait_condition(
                        lambda: identity in self.pending, timeout=remaining
                    )
                except TimeoutError:
                    # 等待超时不视为失败，由循环再次补查状态。
                    pass
        remaining = call.run.deadline_at - workflow.now()
        if remaining.total_seconds() <= 0:
            # 接续前已无剩余时间，不再发起处理 Activity。
            raise ApplicationError("No time left for continuation", non_retryable=True)
        body = await workflow.execute_activity(
            "runtime.wait_handle",
            call.model_dump_json(),
            result_type=str,
            start_to_close_timeout=min(activity_timeout, remaining),
            schedule_to_close_timeout=remaining,
            retry_policy=retry_policy,
        )
        result = Handling.model_validate_json(body)
        if result.state == "failed":
            # 接续处理被业务拒绝，转为不可重试错误。
            raise ApplicationError("Wait continuation rejected", non_retryable=True)
        return result
