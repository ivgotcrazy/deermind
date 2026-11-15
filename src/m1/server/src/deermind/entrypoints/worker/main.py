"""Shared worker process; validate dependencies before publishing local readiness."""

import asyncio
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from deermind.bootstrap.services import create_worker
from deermind.bootstrap.settings import Settings
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.files.check import check_storage
from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest
from temporalio.client import Client

LOGGER = logging.getLogger("runtime")
READY_FILE = Path("/tmp/deermind-worker-ready")


async def run() -> None:
    """SIGTERM stops polling; unexpected worker failure exits the process."""
    READY_FILE.unlink(missing_ok=True)
    settings = Settings.from_environment()
    check_storage(settings.files_root)
    async with asyncio.timeout(15):
        client = await Client.connect(
            settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
        await client.workflow_service.describe_namespace(
            DescribeNamespaceRequest(namespace=settings.temporal_namespace),
        )

    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopped.set)

    # Blocking file I/O runs in the activity pool, not on the asyncio loop.
    with ThreadPoolExecutor(2) as workflow_executor, ThreadPoolExecutor(4) as activity_executor:
        worker = create_worker(client, settings, workflow_executor, activity_executor)
        try:
            async with worker:
                READY_FILE.touch()
                LOGGER.info(
                    "Worker 已启动，等待共享队列任务",
                    extra={"action": "worker_started", "outcome": "success"},
                )
                await stopped.wait()
        finally:
            READY_FILE.unlink(missing_ok=True)
    LOGGER.info("Worker 已停止", extra={"action": "worker_stopped", "outcome": "success"})


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run())
    except Exception:
        LOGGER.exception(
            "Worker 无法继续运行，请检查配置与依赖",
            extra={"action": "worker_failed", "outcome": "failed", "error_code": "WORKER_FAILED"},
        )
        raise SystemExit(1) from None
