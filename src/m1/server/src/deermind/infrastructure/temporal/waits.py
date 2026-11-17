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
            raise ApplicationError(
                "Wait probe rejected", type=type(error).__name__, non_retryable=True
            ) from None

    @activity.defn(name="runtime.wait_handle")
    async def handle(self, body: str) -> str:
        call = WaitCall.model_validate_json(body)
        try:
            return (await self.service.handle(call)).model_dump_json()
        except (ValueError, PermissionError) as error:
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
        while True:
            self.pending.discard(identity)
            remaining = call.run.deadline_at - workflow.now()
            if remaining.total_seconds() <= 0:
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
                break
            remaining = saved.deadline_at - workflow.now()
            if remaining.total_seconds() > 0:
                try:
                    await workflow.wait_condition(
                        lambda: identity in self.pending, timeout=remaining
                    )
                except TimeoutError:
                    pass
        remaining = call.run.deadline_at - workflow.now()
        if remaining.total_seconds() <= 0:
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
            raise ApplicationError("Wait continuation rejected", non_retryable=True)
        return result
