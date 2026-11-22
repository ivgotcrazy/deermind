"""Exercise the deployed codec with isolated databases, files, and real Temporal histories."""

import asyncio
import hashlib
import json
import multiprocessing
import os
import resource
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from multiprocessing.process import BaseProcess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

from deermind.bootstrap.settings import Settings
from deermind.bootstrap.temporal import connect_temporal
from deermind.entrypoints.maintenance.database import upgrade
from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.local import LocalFiles
from deermind.infrastructure.files.payload_codec import (
    ENCODING,
    PayloadReference,
    RuntimePayloadError,
)
from payload_codec_worker import (
    IMAGE,
    MODEL_RESULT,
    NEAR_LIMIT_BYTES,
    PARALLEL_ACTIVITIES,
    AgentWorkflow,
    InlineWorkflow,
    MemoryWorkflow,
    ReplayWorkflow,
    worker_process,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio.api.common.v1 import Payloads
from temporalio.api.enums.v1 import EventType
from temporalio.api.workflowservice.v1 import StartWorkflowExecutionRequest
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowHandle, WorkflowHistory
from temporalio.service import RPCError, RPCStatusCode
from test_database import DatabaseTestCase

RUN_TIMEOUT = timedelta(seconds=150)
RPC_TIMEOUT = timedelta(seconds=8)


def recorded_payloads(history: WorkflowHistory) -> list[Payloads]:
    """Read persisted payload wrappers without passing them through the codec."""
    result: list[Payloads] = []
    for event in history.events:
        match event.event_type:
            case EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED:
                result.append(event.workflow_execution_started_event_attributes.input)
            case EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED:
                result.append(event.activity_task_scheduled_event_attributes.input)
            case EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED:
                result.append(event.activity_task_completed_event_attributes.result)
            case EventType.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED:
                result.append(event.workflow_execution_completed_event_attributes.result)
            case _:
                pass
    return result


def references(payloads: list[Payloads]) -> list[PayloadReference]:
    return [
        PayloadReference.model_validate_json(payload.data)
        for batch in payloads
        for payload in batch.payloads
        if payload.metadata.get("encoding") == ENCODING
    ]


def worker_peak_kib(pid: int) -> int:
    """Linux records a process high-water mark even after large batches are released."""
    stats = Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
    hwm = next(row for row in stats.splitlines() if row.startswith("VmHWM:"))
    return int(hwm.split()[1])


class PayloadCodecIntegrationTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        upgrade(self.migrator)
        root = os.environ.get("M1_TEST_FILES_ROOT")
        temporary = TemporaryDirectory(dir=root)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.settings = Settings(
            files_root=self.root,
            files_backend="local",
            temporal_address=os.environ["M1_TEST_TEMPORAL_ADDRESS"],
            temporal_namespace=os.environ["M1_TEST_TEMPORAL_NAMESPACE"],
            task_queue=f"e0116-{uuid4().hex}",
        )
        self.workflow_ids: list[str] = []

    def workflow_id(self) -> str:
        identifier = f"{self.settings.task_queue}-{uuid4().hex}"
        self.workflow_ids.append(identifier)
        return identifier

    def request_bytes(self, start: Mock) -> int:
        """Measure the exact protobuf passed to the SDK workflow service."""
        call = start.call_args
        assert call is not None
        request = call.args[0]
        assert isinstance(request, StartWorkflowExecutionRequest)
        self.assertLessEqual(request.input.ByteSize(), 1024 * 1024)
        self.assertLess(request.ByteSize(), 4 * 1024 * 1024)
        return request.ByteSize()

    @asynccontextmanager
    async def clients(self) -> AsyncGenerator[tuple[Client, Client, AsyncEngine]]:
        engine = application_engine(self.app)
        raw = await Client.connect(
            self.settings.temporal_address, namespace=self.settings.temporal_namespace
        )
        try:
            yield await connect_temporal(self.settings, engine), raw, engine
        finally:
            try:
                for identifier in self.workflow_ids:
                    handle = raw.get_workflow_handle(identifier)
                    try:
                        status = (await handle.describe(rpc_timeout=RPC_TIMEOUT)).status
                        if status == WorkflowExecutionStatus.RUNNING:
                            await handle.terminate(
                                "isolated E01-16 cleanup", rpc_timeout=RPC_TIMEOUT
                            )
                    except RPCError as error:
                        if error.status != RPCStatusCode.NOT_FOUND:
                            raise
            finally:
                await engine.dispose()

    @asynccontextmanager
    async def worker(self) -> AsyncGenerator[BaseProcess]:
        """Launch a new process and wait for its own ready marker."""
        ready = self.root / f"worker-ready-{uuid4().hex}"
        process = multiprocessing.get_context("spawn").Process(
            target=worker_process, args=(self.app, self.settings, ready)
        )
        clock = asyncio.get_running_loop().time
        started = clock()
        process.start()
        try:
            # Include cold Python and SDK imports in the test Pod's readiness window.
            async with asyncio.timeout(60):
                while not ready.is_file():
                    self.assertTrue(process.is_alive(), f"Worker exited {process.exitcode}")
                    await asyncio.sleep(0.1)
            print(f"E01-16 worker_ready_seconds={clock() - started:.2f}", flush=True)
            yield process
        finally:
            if process.is_alive():
                process.terminate()
            await asyncio.to_thread(process.join, 8)
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, 3)

    async def wait_for_durable_result(self, handle: WorkflowHandle[ReplayWorkflow, bytes]) -> None:
        """Wait until the server has persisted the tool-like first step."""
        async with asyncio.timeout(25):
            while True:
                history = await handle.fetch_history(rpc_timeout=RPC_TIMEOUT)
                if any(
                    event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED
                    for event in history.events
                ):
                    return
                await asyncio.sleep(0.2)

    def test_agent_roundtrip_and_old_inline_history(self) -> None:
        asyncio.run(self.agent_roundtrip_and_old_inline_history())

    async def agent_roundtrip_and_old_inline_history(self) -> None:
        async with self.clients() as (client, raw, _), self.worker():
            old = await raw.start_workflow(
                InlineWorkflow.run,
                b"inline-written-without-codec",
                id=self.workflow_id(),
                task_queue=self.settings.task_queue,
                execution_timeout=RUN_TIMEOUT,
            )
            self.assertEqual(await old.result(), b"inline-written-without-codec")
            current = client.get_workflow_handle(old.id, result_type=bytes)
            self.assertEqual(await current.result(), b"inline-written-without-codec")
            self.assertFalse(references(recorded_payloads(await old.fetch_history())))

            with patch.object(
                client.workflow_service,
                "start_workflow_execution",
                wraps=client.workflow_service.start_workflow_execution,
            ) as start:
                handle = await client.start_workflow(
                    AgentWorkflow.run,
                    IMAGE,
                    id=self.workflow_id(),
                    task_queue=self.settings.task_queue,
                    execution_timeout=RUN_TIMEOUT,
                )
                request_size = self.request_bytes(start)
            self.assertEqual(await handle.result(), MODEL_RESULT)
            history = await raw.get_workflow_handle(handle.id).fetch_history()
            batches = recorded_payloads(history)
            stages = [
                event.activity_task_scheduled_event_attributes.activity_type.name
                for event in history.events
                if event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_SCHEDULED
            ]
            self.assertEqual(
                [name.rsplit("__", 1)[-1] for name in stages],
                ["model_request", "call_tool", "model_request"],
            )

            # Image, tool result and both model turns crossed a real SDK boundary.
            self.assertGreaterEqual(len(references(batches)), 5)
            self.assertLessEqual(max(batch.ByteSize() for batch in batches), 1024 * 1024)
            print(
                "E01-16-wire",
                json.dumps(
                    {
                        "activities": stages,
                        "max_history_event_bytes": max(e.ByteSize() for e in history.events),
                        "max_recorded_batch_bytes": max(batch.ByteSize() for batch in batches),
                        "max_send_batch_bytes": 1024 * 1024,
                        "offloaded_occurrences": len(references(batches)),
                        "start_request_bytes": request_size,
                    }
                ),
                flush=True,
            )

    def test_restart_after_durable_activity(self) -> None:
        asyncio.run(self.restart_after_durable_activity())

    async def restart_after_durable_activity(self) -> None:
        async with self.clients() as (client, raw, _):
            async with self.worker() as first:
                handle = await client.start_workflow(
                    ReplayWorkflow.run,
                    IMAGE,
                    id=self.workflow_id(),
                    task_queue=self.settings.task_queue,
                    execution_timeout=RUN_TIMEOUT,
                )
                await self.wait_for_durable_result(handle)
                first_pid = first.pid

            async with self.worker() as second:
                self.assertNotEqual(first_pid, second.pid)
                await handle.signal(ReplayWorkflow.release, rpc_timeout=RPC_TIMEOUT)
                self.assertEqual(await handle.result(), IMAGE)

            self.assertEqual(
                (self.root / "recorded-calls").read_text(encoding="utf-8").splitlines(),
                [hashlib.sha256(IMAGE).hexdigest()],
            )
            history = await raw.get_workflow_handle(handle.id).fetch_history()
            activity_results = [
                event.activity_task_completed_event_attributes.result
                for event in history.events
                if event.event_type == EventType.EVENT_TYPE_ACTIVITY_TASK_COMPLETED
            ]
            self.assertEqual(len(activity_results), 1)
            # Same complete original Payload is reused in the start input, Activity and result.
            persisted = references(recorded_payloads(history))
            self.assertGreaterEqual(len(persisted), 4)
            self.assertEqual(len({ref.storage_ref for ref in persisted}), 1)

    def test_file_faults_do_not_fake_success(self) -> None:
        asyncio.run(self.file_faults_do_not_fake_success())

    async def file_faults_do_not_fake_success(self) -> None:
        async with self.clients() as (client, raw, engine):
            rejected = self.workflow_id()
            with (
                patch.object(LocalFiles, "save", side_effect=OSError("synthetic disk failure")),
                self.assertRaises(RuntimePayloadError),
            ):
                await client.start_workflow(
                    InlineWorkflow.run,
                    IMAGE,
                    id=rejected,
                    task_queue=self.settings.task_queue,
                    execution_timeout=RUN_TIMEOUT,
                )
            with self.assertRaises(RPCError) as missing:
                await raw.get_workflow_handle(rejected).describe(rpc_timeout=RPC_TIMEOUT)
            self.assertEqual(missing.exception.status, RPCStatusCode.NOT_FOUND)

            async with self.worker():
                handle = await client.start_workflow(
                    InlineWorkflow.run,
                    IMAGE,
                    id=self.workflow_id(),
                    task_queue=self.settings.task_queue,
                    execution_timeout=RUN_TIMEOUT,
                )
                self.assertEqual(await handle.result(), IMAGE)
            history = await raw.get_workflow_handle(handle.id).fetch_history()
            output = history.events[-1].workflow_execution_completed_event_attributes.result
            (reference,) = references([output])
            async with engine.connect() as connection:
                key = await connection.scalar(
                    text("SELECT storage_key FROM runtime.file_objects WHERE file_id=:id"),
                    {"id": reference.storage_ref},
                )
            self.assertIsInstance(key, str)
            assert isinstance(key, str)
            blob = self.root / key
            self.assertTrue(blob.resolve().is_relative_to(self.root.resolve()))
            original = blob.read_bytes()
            moved = blob.with_suffix(".withheld")
            blob.rename(moved)
            try:
                with self.assertRaises(RuntimePayloadError):
                    await handle.result()
            finally:
                moved.rename(blob)
            blob.chmod(0o600)
            try:
                blob.write_bytes(b"x" + original[1:])
                with self.assertRaises(RuntimePayloadError):
                    await handle.result()
            finally:
                blob.write_bytes(original)
                blob.chmod(0o440)
            self.assertEqual(await handle.result(), IMAGE)

    def test_concurrent_near_limit_memory(self) -> None:
        asyncio.run(self.concurrent_near_limit_memory())

    async def concurrent_near_limit_memory(self) -> None:
        async with self.clients() as (client, _, _), self.worker() as process:
            handles = await asyncio.gather(
                *(
                    client.start_workflow(
                        MemoryWorkflow.run,
                        index,
                        id=self.workflow_id(),
                        task_queue=self.settings.task_queue,
                        execution_timeout=RUN_TIMEOUT,
                    )
                    for index in range(PARALLEL_ACTIVITIES)
                )
            )

            async def check_result(
                index: int, handle: WorkflowHandle[MemoryWorkflow, bytes]
            ) -> None:
                data = await handle.result()
                self.assertEqual(len(data), NEAR_LIMIT_BYTES)
                self.assertEqual(data.count(index), NEAR_LIMIT_BYTES)

            await asyncio.gather(*(check_result(index, h) for index, h in enumerate(handles)))

            with patch.object(
                client.workflow_service,
                "start_workflow_execution",
                wraps=client.workflow_service.start_workflow_execution,
            ) as start:
                near_limit = await client.start_workflow(
                    InlineWorkflow.run,
                    b"x" * NEAR_LIMIT_BYTES,
                    id=self.workflow_id(),
                    task_queue=self.settings.task_queue,
                    execution_timeout=RUN_TIMEOUT,
                )
                request_size = self.request_bytes(start)
            result = await near_limit.result()
            self.assertEqual(len(result), NEAR_LIMIT_BYTES)
            self.assertEqual(result.count(b"x"), NEAR_LIMIT_BYTES)
            assert process.pid is not None
            self.assertTrue(process.is_alive())
            peaks = {
                "client_peak_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "worker_peak_kib": worker_peak_kib(process.pid),
                "activity_parallelism": PARALLEL_ACTIVITIES,
                "near_limit_payload_bytes": NEAR_LIMIT_BYTES,
                "near_limit_start_request_bytes": request_size,
            }
            print("E01-16-memory", json.dumps(peaks), flush=True)
            self.assertLess(peaks["client_peak_kib"], 512 * 1024)
            self.assertLess(peaks["worker_peak_kib"], 1536 * 1024)
