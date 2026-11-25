"""显式执行迁移；API和Worker启动不调用此命令。"""

import argparse
import logging
from importlib.resources import files
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from deermind.bootstrap.database import DatabaseSettings
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.database.connection import EXPECTED_REVISION, MAINTENANCE_LOCK
from sqlalchemy import URL, create_engine, text
from sqlalchemy.pool import NullPool

LOGGER = logging.getLogger("runtime")
# 同一业务库共用部署锁；提交、回滚或断连后释放。
MIGRATION_LOCK = MAINTENANCE_LOCK


def migration_config() -> Config:
    """优先读取wheel中的脚本；开发态读取同一份源码，拒绝缺失或分叉的迁移链。"""
    packaged = Path(str(files("deermind"))) / "_migrations"
    source = Path(__file__).resolve().parents[4] / "migrations"
    config = Config()
    config.set_main_option("script_location", str(packaged if packaged.is_dir() else source))
    if ScriptDirectory.from_config(config).get_heads() != [EXPECTED_REVISION]:
        # 迁移链存在分叉、缺失或 head 与应用期望不符，拒绝执行。
        raise RuntimeError("Migration package must have exactly the application's expected head")
    return config


def upgrade(url: URL) -> str | None:
    """在一个事务中升级并返回原版本；失败回滚DDL及版本记录，锁冲突立即退出。"""
    config = migration_config()
    engine = create_engine(
        url, poolclass=NullPool, hide_parameters=True, connect_args={"connect_timeout": 10}
    )
    try:
        with engine.begin() as connection:
            if connection.scalar(text("SELECT current_user")) != "deermind_migrator":
                # 迁移必须使用专用 migrator 账号，避免误用高权限业务账号。
                raise RuntimeError("Migration requires deermind_migrator")
            locked = connection.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK}
            )
            if not locked:
                # 已有另一迁移事务持锁，立即退出而非排队等待。
                raise RuntimeError("Another database migration is running")

            previous = MigrationContext.configure(
                connection, opts={"version_table_schema": "public"}
            ).get_current_revision()
            config.attributes["connection"] = connection
            command.upgrade(config, EXPECTED_REVISION)
            current = MigrationContext.configure(
                connection, opts={"version_table_schema": "public"}
            ).get_current_revision()
            if current != EXPECTED_REVISION:
                # 迁移后版本未落到期望 head，回滚本事务并报错。
                raise RuntimeError("Migration did not reach the expected revision")
        return previous
    finally:
        # 结束后释放临时连接池，咨询锁随事务回滚或提交一并释放。
        engine.dispose()


def main() -> None:
    """从环境读取迁移配置，记录结果；失败时安全输出日志并退出。"""
    parser = argparse.ArgumentParser(description="Upgrade the explicitly configured business DB")
    parser.add_argument("action", choices=["upgrade"])
    parser.parse_args()
    configure_logging()
    try:
        settings = DatabaseSettings.from_environment()
        previous = upgrade(settings.url())
        LOGGER.info(
            "数据库 %s 迁移完成：%s → %s",
            settings.name,
            previous or "empty",
            EXPECTED_REVISION,
            extra={"action": "database_migrated", "outcome": "success"},
        )
    except Exception:
        # 迁移失败：记录后以非零码退出，阻断后续发布。
        LOGGER.exception(
            "数据库迁移失败；停止发布，检查配置、权限和迁移版本",
            extra={
                "action": "database_migration",
                "outcome": "failed",
                "error_code": "MIGRATION_FAILED",
            },
        )
        raise SystemExit(1) from None
