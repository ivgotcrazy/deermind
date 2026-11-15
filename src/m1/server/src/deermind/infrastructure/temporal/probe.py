"""Deployment-only workflow; never registered as a business AI Operation."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn(name="runtime.storage_probe")
class StorageProbe:
    """Read an API-side sentinel and write a reply through a worker Activity."""

    @workflow.run
    async def run(self, token: str) -> str:
        return await workflow.execute_activity(
            "runtime.storage_probe_reply",
            token,
            result_type=str,
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
