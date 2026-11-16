"""PostgreSQL连接及只读版本检查，不执行DDL。"""

from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

EXPECTED_REVISION = "0010_waits_results"
# 迁移及投影维护互斥；普通业务不取得此锁。
MAINTENANCE_LOCK = 47001004
SCHEMAS = ("product", "domain", "interaction", "evaluation", "runtime", "ai")


class DatabaseNotReady(RuntimeError):
    """当前应用不能安全使用该数据库。"""


def application_engine(url: URL) -> AsyncEngine:
    """每个进程一个有限连接池；建池和启动都不执行DDL。"""
    return create_async_engine(
        url,
        pool_size=5,
        max_overflow=0,
        pool_timeout=3,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": (
                "-c statement_timeout=10000 -c lock_timeout=3000 "
                "-c idle_in_transaction_session_timeout=10000"
            ),
        },
    )


async def check_database(engine: AsyncEngine) -> None:
    """拒绝缺失或不匹配的版本，以及误注入的迁移账号。"""
    async with engine.connect() as connection:
        identity = await connection.scalar(text("SELECT current_user"))
        if identity != "deermind_app":
            raise DatabaseNotReady("Application must use deermind_app")

        versions = await connection.scalars(text("SELECT version_num FROM public.alembic_version"))
        if list(versions) != [EXPECTED_REVISION]:
            raise DatabaseNotReady("Database revision does not match this application")

        names = await connection.scalars(
            text("SELECT nspname FROM pg_namespace WHERE nspname = ANY(:names)"),
            {"names": list(SCHEMAS)},
        )
        if set(names) != set(SCHEMAS):
            raise DatabaseNotReady("A required module schema is missing")
