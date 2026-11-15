"""在真实PostgreSQL中验证迁移，只创建和删除隔离的随机测试库。

经scripts/test-database.py指定集群；凭据由测试Pod环境提供。
已有业务库和Temporal库仅用于权限检查，不修改其内容。
"""

import asyncio
import os
import tempfile
import unittest
from contextlib import AsyncExitStack
from unittest.mock import patch
from uuid import uuid4

import psycopg
from alembic import op
from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.maintenance.database import MIGRATION_LOCK, upgrade
from deermind.entrypoints.worker.main import run
from deermind.infrastructure.database.connection import (
    EXPECTED_REVISION,
    SCHEMAS,
    DatabaseNotReady,
    application_engine,
    check_database,
)
from psycopg import sql
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.pool import NullPool


class MigrationTests(unittest.TestCase):
    """验证真实DDL、断连回滚、权限和两类应用启动检查。"""

    def setUp(self) -> None:
        """每个用例创建独立测试库，并立即登记逆序清理。"""
        self.name = "dm_e0104_test_" + uuid4().hex
        self.admin = psycopg.connect(
            host=os.environ["M1_DB_HOST"],
            port=int(os.environ["M1_DB_PORT"]),
            dbname="postgres",
            user="postgres",
            password=os.environ["M1_TEST_ADMIN_PASSWORD"],
            autocommit=True,
            connect_timeout=5,
        )
        self.addCleanup(self.admin.close)
        self.admin.execute(
            sql.SQL("CREATE DATABASE {} OWNER deermind_migrator").format(sql.Identifier(self.name))
        )
        self.addCleanup(self.drop_test_database)
        self.admin.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(self.name))
        )
        self.admin.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO deermind_app").format(
                sql.Identifier(self.name)
            )
        )
        self.migrator = self.url("deermind_migrator", "M1_TEST_MIGRATION_PASSWORD")
        self.app = self.url("deermind_app", "M1_TEST_APP_PASSWORD")
        self.engine = create_engine(self.migrator, poolclass=NullPool, hide_parameters=True)
        self.addCleanup(self.engine.dispose)

    def drop_test_database(self) -> None:
        """仅清理本次生成的数据库名，绝不使用部署配置中的业务库名。"""
        if not self.name.startswith("dm_e0104_test_") or len(self.name) != 46:
            raise RuntimeError("Refusing to remove a non-test database")
        self.admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(self.name))
        )

    def url(self, user: str, password_key: str) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=user,
            password=os.environ[password_key],
            host=os.environ["M1_DB_HOST"],
            port=int(os.environ["M1_DB_PORT"]),
            database=self.name,
        )

    def assert_empty(self) -> None:
        """确认失败迁移没有遗留版本表或部分模块schema。"""
        with self.engine.connect() as connection:
            self.assertIsNone(
                connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            )
            names = connection.scalars(text("SELECT nspname FROM pg_namespace"))
            self.assertFalse(set(names) & set(SCHEMAS))

    def test_empty_upgrade_and_repeat(self) -> None:
        """空库升级及重复升级得到同一版本、字段与所有者。"""
        self.assert_empty()
        self.assertIsNone(upgrade(self.migrator))
        self.assertEqual(upgrade(self.migrator), EXPECTED_REVISION)
        with self.engine.connect() as connection:
            self.assertEqual(
                list(connection.scalars(text("SELECT version_num FROM public.alembic_version"))),
                [EXPECTED_REVISION],
            )
            columns = connection.execute(
                text(
                    "SELECT column_name, data_type, character_maximum_length, is_nullable "
                    "FROM information_schema.columns WHERE table_schema='public' "
                    "AND table_name='alembic_version'"
                )
            ).all()
            self.assertEqual(columns, [("version_num", "character varying", 32, "NO")])
            owners = connection.execute(
                text(
                    "SELECT nspname, pg_get_userbyid(nspowner) FROM pg_namespace "
                    "WHERE nspname = ANY(:names)"
                ),
                {"names": list(SCHEMAS)},
            ).all()
            self.assertEqual(set(owners), {(name, "deermind_migrator") for name in SCHEMAS})
        asyncio.run(self.verify_ready())

    async def verify_ready(self) -> None:
        """以运行账号检查数据库，结束后释放全部连接。"""
        engine = application_engine(self.app)
        try:
            await check_database(engine)
        finally:
            await engine.dispose()

    def test_pool_limit_and_database_timeouts(self) -> None:
        """检查实际数据库限时和第六条连接被拒的行为。"""
        upgrade(self.migrator)
        asyncio.run(self.verify_pool())

    async def verify_pool(self) -> None:
        """占用全部五条连接，核对会话参数和池等待超时。"""
        engine = application_engine(self.app)
        try:
            async with AsyncExitStack() as stack:
                connections = [await stack.enter_async_context(engine.connect()) for _ in range(5)]
                values = await connections[0].execute(
                    text(
                        "SELECT current_setting('statement_timeout'), "
                        "current_setting('lock_timeout'), "
                        "current_setting('idle_in_transaction_session_timeout')"
                    )
                )
                self.assertEqual(values.one(), ("10s", "3s", "10s"))
                # 第六次取连接必须超时，不能悄悄超出五连接上限。
                with self.assertRaises(PoolTimeout):
                    async with engine.connect():
                        self.fail("Connection pool exceeded the five-connection limit")
        finally:
            await engine.dispose()

    def test_application_permissions(self) -> None:
        """应用不能执行DDL或篡改版本，不能冒用迁移入口。"""
        upgrade(self.migrator)
        engine = create_engine(self.app, poolclass=NullPool)
        try:
            for statement in (
                "CREATE SCHEMA unauthorized",
                "CREATE TABLE runtime.unauthorized (id integer)",
                "UPDATE public.alembic_version SET version_num='wrong'",
                "DELETE FROM public.alembic_version",
            ):
                with self.subTest(statement=statement), self.assertRaises(DBAPIError) as denied:
                    with engine.begin() as connection:
                        connection.execute(text(statement))
                self.assertIn("permission denied", str(denied.exception.orig))
            with self.assertRaisesRegex(RuntimeError, "requires deermind_migrator"):
                upgrade(self.app)
        finally:
            engine.dispose()

    def test_concurrent_migration_rejected(self) -> None:
        """另一迁移持锁时立即退出，释放后可以升级。"""
        with self.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK})
            with self.assertRaisesRegex(RuntimeError, "Another database migration"):
                upgrade(self.migrator)
        self.assert_empty()
        upgrade(self.migrator)

    def test_interrupted_migration_rolls_back(self) -> None:
        """强制断开DDL连接后整批回滚，随后能够重新升级。"""
        original = op.execute

        def interrupt(statement: str) -> None:
            if statement.startswith('CREATE SCHEMA "evaluation"'):
                pid = op.get_bind().scalar(text("SELECT pg_backend_pid()"))
                self.admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
            original(statement)

        with patch("alembic.op.execute", side_effect=interrupt), self.assertRaises(DBAPIError):
            upgrade(self.migrator)
        self.assert_empty()
        upgrade(self.migrator)

    def test_unknown_schema_is_not_silently_adopted(self) -> None:
        """来源不明的schema阻止初始化，原对象保持不变。"""
        with self.engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA domain"))
        with self.assertRaises(DBAPIError):
            upgrade(self.migrator)
        with self.engine.connect() as connection:
            self.assertIsNone(connection.scalar(text("SELECT to_regnamespace('product')")))
            self.assertIsNotNone(connection.scalar(text("SELECT to_regnamespace('domain')")))
            self.assertIsNone(
                connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            )

    def test_missing_or_incompatible_revision_blocks_services(self) -> None:
        """缺少版本或版本不符时API和Worker都不能启动。"""
        for revision in (None, "unknown_revision", EXPECTED_REVISION):
            if revision == "unknown_revision":
                upgrade(self.migrator)
                with self.engine.begin() as connection:
                    connection.execute(
                        text("UPDATE public.alembic_version SET version_num=:v"), {"v": revision}
                    )
            elif revision == EXPECTED_REVISION:
                with self.engine.begin() as connection:
                    connection.execute(
                        text("UPDATE public.alembic_version SET version_num=:v"), {"v": revision}
                    )
            with tempfile.TemporaryDirectory() as directory, self.subTest(revision=revision):
                environment = {
                    "M1_DB_HOST": str(self.app.host),
                    "M1_DB_PORT": str(self.app.port),
                    "M1_DB_NAME": self.name,
                    "M1_DB_USER": "deermind_app",
                    "M1_DB_PASSWORD": str(self.app.password),
                    "M1_FILES_ROOT": directory,
                    "M1_TEMPORAL_ADDRESS": "127.0.0.1:1",
                    "M1_TEMPORAL_NAMESPACE": "dm-test",
                    "M1_TASK_QUEUE": "test",
                }
                with patch.dict(os.environ, environment):
                    if revision == EXPECTED_REVISION:
                        asyncio.run(self.verify_ready())
                    else:
                        asyncio.run(self.assert_services_reject())

    async def assert_services_reject(self) -> None:
        """API失败且Worker不接触Temporal，避免先拉任务后发现数据库错误。"""
        app = create_app()
        with self.assertLogs("runtime", level="ERROR"), self.assertRaises(RuntimeError):
            async with app.router.lifespan_context(app):
                self.fail("API started with incompatible schema")
        with patch("deermind.entrypoints.worker.main.Client.connect") as connect:
            with self.assertRaises((DBAPIError, DatabaseNotReady)):
                await run()
            connect.assert_not_called()

    def test_temporal_cannot_connect_to_business_database(self) -> None:
        """核对明确的权限拒绝，不能用网络错误冒充账号隔离通过。"""
        for user, key in (
            ("temporal", "M1_TEST_TEMPORAL_PASSWORD"),
            ("temporal_visibility", "M1_TEST_VISIBILITY_PASSWORD"),
        ):
            with self.subTest(user=user), self.assertRaises(psycopg.OperationalError) as denied:
                with psycopg.connect(
                    host=self.app.host,
                    port=self.app.port,
                    dbname="deermind",
                    user=user,
                    password=os.environ[key],
                    connect_timeout=5,
                ):
                    self.fail("Temporal account accessed business database")
            self.assertIn('permission denied for database "deermind"', str(denied.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
