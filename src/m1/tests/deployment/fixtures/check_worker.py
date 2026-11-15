"""Run over kubectl stdin inside the API container; inspect real SDK assembly."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from deermind.bootstrap.services import create_worker
from deermind.bootstrap.settings import Settings
from deermind.infrastructure.temporal.probe import StorageProbe
from deermind.infrastructure.temporal.probe_activity import ProbeActivity
from temporalio.client import Client
from temporalio.worker import Worker


async def main() -> None:
    settings = Settings.from_environment()
    async with asyncio.timeout(20):
        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
    with ThreadPoolExecutor(2) as workflows, ThreadPoolExecutor(4) as activities:
        worker = create_worker(client, settings, workflows, activities)
        assert worker.task_queue == settings.task_queue
        try:
            Worker(
                client,
                task_queue=settings.task_queue,
                workflows=[StorageProbe, StorageProbe],
                workflow_task_executor=workflows,
            )
        except ValueError as error:
            assert "More than one workflow" in str(error)
        else:
            raise AssertionError("Duplicate workflow was accepted")
        probe = ProbeActivity(settings.files_root)
        try:
            Worker(
                client,
                task_queue=settings.task_queue,
                activities=[probe.reply, probe.reply],
                activity_executor=activities,
            )
        except ValueError as error:
            assert "More than one activity" in str(error)
        else:
            raise AssertionError("Duplicate activity was accepted")
    print("PASS: real SDK assembly; duplicate workflow and activity rejected")


asyncio.run(main())
