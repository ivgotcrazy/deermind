"""显式维护命令；不自动停服务，不从事件启动业务工作，不输出正文或凭据。"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
from uuid import UUID

from deermind.bootstrap.database import DatabaseSettings
from deermind.bootstrap.projections import account_rebuilder
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.files.local import LocalFiles
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

LOGGER = logging.getLogger("runtime")


async def run(args: argparse.Namespace) -> int:
    """凭据来自显式环境；维护身份检查由重建器在接触投影前执行。"""
    settings = DatabaseSettings.from_environment()
    backend = os.environ.get("M1_FILES_BACKEND", "pvc")
    if backend != "local" and backend != "pvc":
        raise ValueError("Maintenance file backend must be local or pvc")
    files = LocalFiles(Path(os.environ["M1_FILES_ROOT"]), backend=backend)
    engine = create_async_engine(
        settings.url(),
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={"connect_timeout": 5},
    )
    try:
        service = account_rebuilder(engine, files)
        if args.action == "prepare":
            if args.generation is None or not args.scope:
                raise ValueError("Prepare requires generation and explicit scopes")
            job = await service.prepare(
                args.rebuild_id,
                args.generation,
                args.scope,
                operator=args.operator,
                authorization=args.authorization,
            )
        elif args.action == "resume":
            job = await service.resume(
                args.rebuild_id,
                operator=args.operator,
                authorization=args.authorization,
                max_events=args.max_events,
            )
        else:
            job = await service.status(
                args.rebuild_id, operator=args.operator, authorization=args.authorization
            )
        LOGGER.info(
            "投影维护：%s，状态：%s",
            job.rebuild_id,
            job.state,
            extra={"action": "projection_rebuild", "outcome": job.state},
        )
        print(job.model_dump_json())
        return 1 if job.state == "failed" else 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the registered account query projection")
    parser.add_argument("action", choices=["prepare", "resume", "status"])
    parser.add_argument("--rebuild-id", type=UUID, required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--maintenance-confirmed", action="store_true", required=True)
    parser.add_argument("--generation", type=int)
    parser.add_argument("--scope", type=UUID, action="append")
    parser.add_argument("--max-events", type=int)
    args = parser.parse_args()
    if args.action != "prepare" and (args.generation is not None or args.scope):
        parser.error("Resume/status use the stored scope; do not provide a new scope or generation")
    if args.action != "resume" and args.max_events is not None:
        parser.error("max-events only applies to resume")
    configure_logging()
    try:
        result = asyncio.run(run(args))
    except Exception as error:
        # Schema错误可能含事实原文，不能把异常文本或traceback直接打印。
        LOGGER.error(
            "维护命令未完成（%s）；核对目标、权限、维护窗口及原记录",
            type(error).__name__,
            extra={
                "action": "projection_rebuild",
                "outcome": "failed",
                "error_code": "REBUILD_NOT_COMPLETED",
            },
        )
        result = 1
    raise SystemExit(result)


if __name__ == "__main__":
    main()
