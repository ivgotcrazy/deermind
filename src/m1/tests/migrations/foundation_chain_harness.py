"""E01-18 可由浏览器或协议测试驱动的隔离运行与验收。"""

import asyncio
import json
import os
import signal
import socket
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from deermind.infrastructure.database.connection import application_engine
from deermind.infrastructure.files.payload_codec import PayloadReference
from foundation_chain import ChainFixture, durable_counts, migrated_fixture
from foundation_chain_data import ACTION, ENTRY_NAME, EXPECTED_SHA, INPUT_EVENT, RESULT_EVENT
from foundation_chain_worker import release, wait_checkpoint, worker
from pydantic import JsonValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.service import RPCError, RPCStatusCode
from test_database import DatabaseTestCase
from test_realtime_integration import Endpoint, serve


@dataclass(frozen=True)
class Work:
    request_id: str
    receipt_ref: UUID
    input_event: UUID
    execution_id: UUID
    attempt_id: UUID
    workflow_id: str
    temporal_run_id: str


COUNT_FIELDS = (
    "request_receipt",
    "input_fact",
    "published_notice",
    "subscription_receipt",
    "execution",
    "attempt",
    "start_handoff",
    "result_fact",
    "result_projection",
)


@asynccontextmanager
async def running(
    database: DatabaseTestCase,
    scope: UUID,
    proxy_origin: str | None = None,
    listen_port: int = 0,
) -> AsyncGenerator[tuple[ChainFixture, Endpoint]]:
    """API、隔离主题和 Worker 测试数据由同一次运行持有。"""
    shared = Path(os.environ["M1_TEST_FILES_ROOT"])
    with (
        tempfile.TemporaryDirectory(prefix="e01-18-", dir=shared) as directory,
        socket.socket() as listener,
    ):
        listener.bind(("127.0.0.1", listen_port))
        address = Endpoint(f"http://127.0.0.1:{listener.getsockname()[1]}", listener)
        fixture = ChainFixture(database, scope, Path(directory), proxy_origin or address.origin)
        with patch.dict("os.environ", fixture.env):
            try:
                async with serve(fixture, address):
                    completed: dict[Work, PayloadReference] = {}
                    async with asyncio.TaskGroup() as tasks:
                        driver = tasks.create_task(drive(fixture, completed))
                        try:
                            yield fixture, address
                        finally:
                            driver.cancel()
                    await final_audit(fixture, completed)
            finally:
                await cleanup_workflows(fixture)


async def cleanup_workflows(fixture: ChainFixture) -> None:
    """关闭交接后，只结束本隔离库登记的未完成 Workflow。"""
    engine = application_engine(fixture.database.app)
    try:
        async with engine.connect() as connection:
            pending = (
                await connection.execute(
                    text(
                        "SELECT a.workflow_id,a.temporal_run_id FROM runtime.execution_attempts a "
                        "JOIN runtime.executions e USING (execution_id) "
                        "WHERE e.entry_ref=:entry AND e.scope_id=:scope"
                    ),
                    {"entry": ENTRY_NAME, "scope": fixture.scope},
                )
            ).all()
    finally:
        await engine.dispose()
    if not pending:
        return
    async with asyncio.timeout(15):
        raw = await Client.connect(
            fixture.settings.temporal_address, namespace=fixture.settings.temporal_namespace
        )
        for workflow_id, run_id in pending:
            try:
                handle = raw.get_workflow_handle(workflow_id, run_id=run_id)
                if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
                    await handle.terminate(reason="E01-18 isolated fixture cleanup")
            except RPCError as error:
                if error.status not in {RPCStatusCode.NOT_FOUND, RPCStatusCode.FAILED_PRECONDITION}:
                    raise


async def next_work(engine: AsyncEngine, seen: set[UUID]) -> Work:
    """从已持久化的启动配置取得工作身份，未交接完成时继续等待。"""
    while True:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT r.request_id,r.request_ref, CAST(e.acceptance_key AS uuid), "
                        "e.execution_id,a.attempt_id,a.workflow_id,a.temporal_run_id "
                        "FROM runtime.executions e JOIN runtime.execution_attempts a "
                        "ON a.attempt_id=e.active_attempt_id JOIN product.command_receipt r "
                        "ON r.result_ref ->> 'id'=e.acceptance_key "
                        "WHERE e.entry_ref=:entry AND r.action=:action "
                        "AND a.temporal_run_id IS NOT NULL "
                        "ORDER BY e.created_at"
                    ),
                    {"entry": ENTRY_NAME, "action": ACTION},
                )
            ).all()
        for row in rows:
            if row[3] not in seen:
                return Work(*row)
        await asyncio.sleep(0.1)


async def drive(fixture: ChainFixture, completed: dict[Work, PayloadReference]) -> None:
    """让真实 Worker 在两个固定步骤之间恢复；只控制测试工作的闸门。"""
    engine: AsyncEngine = fixture.app.state.database
    raw = await Client.connect(
        fixture.settings.temporal_address, namespace=fixture.settings.temporal_namespace
    )
    seen: set[UUID] = set()
    args = (fixture.database.app, fixture.settings, fixture.scope, fixture.deployment)
    while True:
        async with worker(*args) as first:
            work = await next_work(engine, seen)
            refs = await wait_checkpoint(raw, work.workflow_id)
            before = await saved_steps(engine, work.execution_id)
            assert before == [("prepare", EXPECTED_SHA)]
            recovery = work.request_id == fixture.recovery_request
            before_pid = first.pid
            if recovery:
                first.kill()
                await asyncio.to_thread(first.join, 8)
                assert not first.is_alive()
                async with worker(*args) as replacement:
                    assert replacement.pid != before_pid
                    after_pid = replacement.pid
                    # 发布恢复信号前确认仍是原工作和原运行。
                    assert await next_work(engine, seen) == work
                    assert await saved_steps(engine, work.execution_id) == before
                    result = await finish(raw, work, refs[0].storage_ref)
            else:
                after_pid = before_pid
                result = await finish(raw, work, refs[0].storage_ref)
            assert result == work.temporal_run_id
            details = await verify_commits(engine, work, refs[0].sha256, refs[0].storage_ref)
            details.update(
                worker_pid_before=before_pid,
                worker_pid_after=after_pid,
                scenario="recovery" if recovery else "normal",
            )
            completed[work] = refs[0]
            print(json.dumps(details, ensure_ascii=False), flush=True)
            seen.add(work.execution_id)


async def finish(raw: Client, work: Work, storage_ref: UUID) -> str | None:
    await release(raw, work.workflow_id)
    async with asyncio.timeout(70):
        handle = raw.get_workflow_handle(work.workflow_id)
        await handle.result()
        described = await handle.describe()
    latest = await wait_checkpoint(raw, work.workflow_id)
    assert latest[0].storage_ref == storage_ref
    return described.run_id


async def saved_steps(engine: AsyncEngine, execution_id: UUID) -> list[tuple[str, str]]:
    async with engine.connect() as connection:
        values = (
            await connection.execute(
                text(
                    "SELECT step_name,output_ref ->> 'id' FROM runtime.step_results "
                    "WHERE execution_id=:id ORDER BY step_name"
                ),
                {"id": execution_id},
            )
        ).all()
    return [(row[0], row[1]) for row in values]


async def verify_commits(
    engine: AsyncEngine, work: Work, encoded_hash: str, storage_ref: UUID
) -> dict[str, JsonValue]:
    """核对事实、收据、派发与两个步骤，所有标识来自真实组件记录。"""
    assert await saved_steps(engine, work.execution_id) == [
        ("prepare", EXPECTED_SHA),
        ("verify", EXPECTED_SHA),
    ]
    async with engine.connect() as connection:
        parameters = {
            "input": work.input_event,
            "receipt": work.receipt_ref,
            "execution": work.execution_id,
            "attempt": work.attempt_id,
            "result_event": RESULT_EVENT,
            "input_event": INPUT_EVENT,
            "file": storage_ref,
            "request": work.request_id,
        }
        counts = (
            await connection.execute(
                text(
                    "SELECT"
                    " (SELECT count(*) FROM product.command_receipt WHERE request_ref=:receipt),"
                    " (SELECT count(*) FROM runtime.events WHERE event_type=:input_event "
                    " AND correlation_id=:receipt AND source_request_id=:request),"
                    " (SELECT count(*) FROM runtime.handoffs WHERE delivery_id=:input "
                    " AND kind='publish' AND state='delivered' AND stream_sequence IS NOT NULL),"
                    " (SELECT count(*) FROM runtime.subscription_receipts WHERE event_id=:input "
                    " AND disposition='accepted' AND arrangement_refs @> "
                    " jsonb_build_array(jsonb_build_object('id',CAST(:execution AS text)))),"
                    " (SELECT count(*) FROM runtime.executions "
                    " WHERE acceptance_key=CAST(:input AS text)"
                    " AND entry_ref='product.foundation_chain'),"
                    " (SELECT count(*) FROM runtime.execution_attempts "
                    " WHERE execution_id=:execution),"
                    " (SELECT count(*) FROM runtime.handoffs WHERE kind='start' AND "
                    " logical_key=CAST(:attempt AS text) AND state='delivered'),"
                    " (SELECT count(*) FROM runtime.events WHERE event_type=:result_event"
                    " AND correlation_id=:receipt AND causation_event_id=:input "
                    " AND source_execution_ref=:execution),"
                    " (SELECT count(*) FROM product.foundation_chain_results "
                    " WHERE execution_id=:execution)"
                ),
                parameters,
            )
        ).one()
        assert tuple(counts) == (1,) * 9, counts
        result = (
            await connection.execute(
                text(
                    "SELECT r.source_event_id,r.sha256 FROM product.foundation_chain_results r "
                    "JOIN runtime.projection_receipts p ON p.event_id=r.source_event_id "
                    "AND p.projector_id='product.foundation_chain' "
                    "WHERE r.execution_id=:execution AND r.input_event_id=:input"
                ),
                parameters,
            )
        ).one()
        saved_hash = await connection.scalar(
            text(
                "SELECT sha256 FROM runtime.file_objects "
                "WHERE file_id=:file AND category='sdk_payload'"
            ),
            parameters,
        )
    assert saved_hash == encoded_hash and result[1] == EXPECTED_SHA
    return {
        "request_id": work.request_id,
        "receipt_ref": str(work.receipt_ref),
        "trigger_event": str(work.input_event),
        "execution_ref": str(work.execution_id),
        "attempt_ref": str(work.attempt_id),
        "workflow_id": work.workflow_id,
        "temporal_run_id": work.temporal_run_id,
        "result_event": str(result[0]),
        "codec_ref": str(storage_ref),
        "codec_hash": encoded_hash,
        "payload_sha256": EXPECTED_SHA,
        "prepare_completions": 1,
        "verified_once": dict(zip(COUNT_FIELDS, counts, strict=True)),
    }


async def final_audit(fixture: ChainFixture, completed: dict[Work, PayloadReference]) -> None:
    """浏览器完成重放与再次提交后，独立复查四条工作的全部逻辑计数。"""
    engine: AsyncEngine = fixture.app.state.database
    async with engine.connect() as connection:
        totals = await durable_counts(connection)
    assert len(completed) == 4
    assert totals == {"receipts": 4, "input_facts": 4, "executions": 4, "handoffs": 8}
    audited = {}
    for work, reference in completed.items():
        verified = await verify_commits(engine, work, reference.sha256, reference.storage_ref)
        audited[work.request_id] = verified["verified_once"]
    print(json.dumps({"final_audit": audited, "totals": totals}), flush=True)


async def browser_loop(database: DatabaseTestCase, scope: UUID) -> None:
    origin = os.environ.get("M1_TEST_WS_BROWSER_ORIGIN", "https://127.0.0.1:5196")
    port = int(os.environ.get("M1_TEST_WS_BROWSER_PORT", "5197"))
    async with running(database, scope, origin, port):
        print("E01-18 fixture ready", flush=True)
        done = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, done.set)
        await done.wait()


def main() -> None:
    database = DatabaseTestCase()
    try:
        database.setUp()
        scope = migrated_fixture(database)
        asyncio.run(browser_loop(database, scope))
    finally:
        database.doCleanups()


if __name__ == "__main__":
    main()
