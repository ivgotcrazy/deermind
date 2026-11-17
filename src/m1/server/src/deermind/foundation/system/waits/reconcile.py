"""底座补查遗漏通知；技术适配不读写等待表。"""

import asyncio
import logging
from uuid import UUID

from deermind.abstractions.executions import RunInput
from deermind.foundation.system.executions import store
from deermind.foundation.system.waits import facts, notifications
from deermind.foundation.system.waits.service import Waits
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

LOGGER = logging.getLogger("runtime")


async def reconcile(
    engine: AsyncEngine, waits: Waits, *, timeout_seconds: int, after: UUID | None = None
) -> UUID | None:
    """补查漏通知；每批100条，失败保留记录，不把读取失败当超时。"""
    async with engine.connect() as connection:
        identities = (
            await connection.scalars(
                text(
                    "SELECT w.wait_id FROM runtime.waits w "
                    "JOIN runtime.wait_handling h USING(wait_id) "
                    "JOIN runtime.executions e ON e.execution_id=w.execution_id "
                    "WHERE h.state IN ('awaiting','cancelled') "
                    "AND e.state IN ('ready','running','waiting') "
                    "AND (CAST(:after AS uuid) IS NULL OR w.wait_id>CAST(:after AS uuid)) "
                    "ORDER BY w.wait_id LIMIT 100"
                ),
                {"after": after},
            )
        ).all()
    for identity in identities:
        try:
            async with asyncio.timeout(timeout_seconds), engine.begin() as connection:
                saved = await facts.read_wait(connection, str(identity))
                execution = await store.load(connection, saved.execution_id)
                if execution.active_attempt_id is None:
                    continue
                current = await store.attempt(connection, execution.active_attempt_id)
                run = RunInput(
                    execution_id=execution.execution_id,
                    attempt_id=current.attempt_id,
                    input_ref=execution.input_ref,
                    implementation_ref=execution.implementation_ref,
                    ai_config_ref=execution.ai_config_ref,
                    deadline_at=current.deadline_at,
                )
                saved = await waits.probe(connection, run, identity)
                handling = await facts.read_handling(connection, saved)
                if saved.resolution != "pending" or handling.state == "cancelled":
                    await notifications.arrange(
                        connection, waits.entries, execution, saved, "reconcile:" + saved.resolution
                    )
        except Exception:
            LOGGER.exception(
                "等待补查失败，保留原等待",
                extra={
                    "action": "wait_reconcile",
                    "outcome": "failed",
                    "wait_id": str(identity),
                },
            )
    return identities[-1] if len(identities) == 100 else None


async def run_reconciler(
    engine: AsyncEngine,
    waits: Waits,
    stopped: asyncio.Event,
    *,
    interval: int,
    timeout_seconds: int,
) -> None:
    after = None
    while not stopped.is_set():
        try:
            after = await reconcile(engine, waits, timeout_seconds=timeout_seconds, after=after)
        except Exception:
            LOGGER.exception(
                "等待补查暂不可用",
                extra={
                    "action": "wait_reconcile",
                    "outcome": "failed",
                },
            )
        await asyncio.sleep(interval)
