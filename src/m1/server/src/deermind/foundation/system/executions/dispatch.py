"""启动/取消的短租约；共享既有交接表，和消息发布保持各自重试预算。"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from deermind.foundation.system.events.contracts import Ref
from deermind.foundation.system.executions.contracts import Dispatch, Limits
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class Lease:
    handoff_id: UUID
    kind: Literal["start", "cancel"]
    owner: str
    attempt_no: int
    deadline: datetime
    command: Dispatch


async def claim(engine: AsyncEngine, limits: Limits) -> Lease | None:
    """取一份到期命令，进程重启不清次数；到上限后留给故障核对收尾。"""
    async with engine.begin() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT * FROM runtime.handoffs WHERE kind IN ('start','cancel') AND "
                        "((state='pending' AND next_attempt_at<=clock_timestamp()) OR "
                        "(state='leased' AND lease_until<=clock_timestamp())) "
                        "ORDER BY next_attempt_at,handoff_id FOR UPDATE SKIP LOCKED LIMIT 1"
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        count, first = (
            await connection.execute(
                text(
                    "SELECT count(*),min(started_at) FROM runtime.handoff_attempts "
                    "WHERE handoff_id=:id"
                ),
                {"id": row["handoff_id"]},
            )
        ).one()
        now = await connection.scalar(text("SELECT clock_timestamp()"))
        deadline = (first or now) + timedelta(seconds=limits.budget_seconds)
        if count >= limits.attempts or now >= deadline:
            await connection.execute(
                text(
                    "UPDATE runtime.handoffs SET state='exhausted',"
                    "lease_owner=NULL,lease_until=NULL "
                    "WHERE handoff_id=:id"
                ),
                {"id": row["handoff_id"]},
            )
            return None
        owner = str(uuid4())
        await connection.execute(
            text(
                "UPDATE runtime.handoffs SET state='leased',lease_owner=:owner,"
                "lease_until=clock_timestamp()+:duration WHERE handoff_id=:id"
            ),
            {
                "id": row["handoff_id"],
                "owner": owner,
                "duration": timedelta(seconds=limits.lease_seconds),
            },
        )
        await connection.execute(
            text(
                "INSERT INTO runtime.handoff_attempts (handoff_id,attempt_no,started_at,outcome) "
                "VALUES (:id,:number,clock_timestamp(),'unknown')"
            ),
            {"id": row["handoff_id"], "number": count + 1},
        )
        return Lease(
            row["handoff_id"],
            row["kind"],
            owner,
            count + 1,
            deadline,
            Dispatch.model_validate_json(json.dumps(row["payload"])),
        )


async def finish(
    engine: AsyncEngine,
    lease: Lease,
    *,
    run_id: str | None = None,
    success: bool,
    error_code: str | None = None,
) -> bool:
    """只允许当前租约写回执；启动回执不得把已完成或停止的业务改回running。"""
    async with engine.begin() as connection:
        # 与受理/停止一致：先工作，再交接行，避免相反锁序造成死锁。
        await connection.execute(
            text("SELECT execution_id FROM runtime.executions WHERE execution_id=:id FOR UPDATE"),
            {"id": lease.command.run.execution_id},
        )
        current = (
            await connection.execute(
                text(
                    "SELECT state,lease_owner,lease_until>clock_timestamp() FROM runtime.handoffs "
                    "WHERE handoff_id=:id FOR UPDATE"
                ),
                {"id": lease.handoff_id},
            )
        ).one()
        if current != ("leased", lease.owner, True):
            return False
        await connection.execute(
            text(
                "UPDATE runtime.handoff_attempts SET finished_at=clock_timestamp(),"
                "outcome=:outcome,"
                "error=CAST(:error AS jsonb),transport_receipt=CAST(:receipt AS jsonb) "
                "WHERE handoff_id=:id AND attempt_no=:number"
            ),
            {
                "id": lease.handoff_id,
                "number": lease.attempt_no,
                "outcome": "delivered" if success else "unknown",
                "error": None
                if success
                else json.dumps({"code": error_code or "DISPATCH_UNKNOWN"}),
                "receipt": Ref(
                    owner="runtime",
                    type="temporal_execution",
                    id=lease.command.workflow_id,
                    path=run_id,
                ).model_dump_json()
                if success
                else None,
            },
        )
        await connection.execute(
            text(
                "UPDATE runtime.handoffs SET state=:state,lease_owner=NULL,lease_until=NULL,"
                "next_attempt_at=clock_timestamp()+:delay WHERE handoff_id=:id"
            ),
            {
                "id": lease.handoff_id,
                "state": "delivered" if success else "pending",
                "delay": timedelta(seconds=(2, 5, 10, 20)[min(lease.attempt_no - 1, 3)]),
            },
        )
        if run_id is not None:
            await connection.execute(
                text(
                    "UPDATE runtime.execution_attempts SET temporal_run_id=:run "
                    "WHERE attempt_id=:id AND (temporal_run_id IS NULL OR temporal_run_id=:run)"
                ),
                {"id": lease.command.run.attempt_id, "run": run_id},
            )
        return True
