"""Explicit operator commands for namespace setup and E01-03 smoke verification."""

import argparse
import asyncio
import logging
from datetime import timedelta
from uuid import uuid4

from deermind.bootstrap.database import database_lifespan
from deermind.bootstrap.settings import Settings
from deermind.bootstrap.temporal import connect_temporal
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.temporal.probe import StorageProbe
from google.protobuf.duration_pb2 import Duration
from temporalio.api.workflowservice.v1 import DescribeNamespaceRequest, RegisterNamespaceRequest
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode

LOGGER = logging.getLogger("runtime")


async def initialize(client: Client, settings: Settings) -> None:
    """Create only the explicitly configured namespace; never alter an existing one."""
    try:
        response = await client.workflow_service.describe_namespace(
            DescribeNamespaceRequest(namespace=settings.temporal_namespace),
        )
    except RPCError as error:
        if error.status != RPCStatusCode.NOT_FOUND:
            raise
        await client.workflow_service.register_namespace(
            RegisterNamespaceRequest(
                namespace=settings.temporal_namespace,
                workflow_execution_retention_period=Duration(seconds=30 * 86400),
            ),
        )
    else:
        if response.config.workflow_execution_retention_ttl.seconds != 30 * 86400:
            raise ValueError("Existing namespace retention differs from the approved 30 days")


async def probe(client: Client, settings: Settings) -> None:
    """Run from the API container to prove worker execution and both PVC directions."""
    token = uuid4().hex
    request = settings.files_root / f".probe-{token}.request"
    reply = settings.files_root / f".probe-{token}.reply"
    try:
        request.write_text(token, encoding="utf-8")
        result = await client.execute_workflow(
            StorageProbe.run,
            token,
            id=f"e01-03-{token}",
            task_queue=settings.task_queue,
            execution_timeout=timedelta(seconds=30),
        )
        if result != token or reply.read_text(encoding="utf-8") != token:
            raise ValueError("Worker result or shared reply mismatch")
        LOGGER.info(
            "测试任务完成，API 与 Worker 共享卷双向读写通过",
            extra={
                "action": "deployment_probe",
                "outcome": "success",
                "execution_id": f"e01-03-{token}",
            },
        )
    finally:
        request.unlink(missing_ok=True)
        reply.unlink(missing_ok=True)


async def run(command: str) -> None:
    settings = Settings.from_environment()
    async with asyncio.timeout(45):
        if command == "init-namespace":
            client = await Client.connect(
                settings.temporal_address,
                namespace=settings.temporal_namespace,
            )
            await initialize(client, settings)
        else:
            async with database_lifespan() as engine:
                await probe(await connect_temporal(settings, engine), settings)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init-namespace", "run"))
    args = parser.parse_args()
    configure_logging()
    try:
        asyncio.run(run(args.command))
    except Exception:
        LOGGER.exception(
            "部署检查失败，请检查目标配置及服务状态",
            extra={
                "action": "deployment_probe",
                "outcome": "failed",
                "error_code": "DEPLOYMENT_PROBE_FAILED",
            },
        )
        raise SystemExit(1) from None
