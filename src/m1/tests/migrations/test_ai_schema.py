"""E01-15 AI表结构验证；只创建隔离测试库，不部署模型调用。"""

from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.ai.facts import MODELS
from sqlalchemy import text
from test_database import DatabaseTestCase


class AISchemaTests(DatabaseTestCase):
    def test_columns_permissions_and_repeat_migration(self) -> None:
        """物理列与完整事实DTO一一对应；配置、候选不可更新，任何表不能删除。"""
        upgrade(self.migrator)
        upgrade(self.migrator)
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.scalar(text("SELECT version_num FROM public.alembic_version")),
                "0011_ai_calls",
            )
            names = connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname='ai' ORDER BY tablename")
            ).all()
            self.assertEqual(
                set(names), {name.split(".")[1] for name in MODELS} | {"execution_usage"}
            )
            for name, model in MODELS.items():
                with self.subTest(table=name):
                    columns = set(
                        connection.scalars(
                            text(
                                "SELECT column_name FROM information_schema.columns "
                                "WHERE table_schema='ai' AND table_name=:table"
                            ),
                            {"table": name.split(".")[1]},
                        )
                    )
                    self.assertEqual(columns, set(model.model_fields) | {"source_event_id"})
                    self.assertFalse(
                        connection.scalar(
                            text("SELECT has_table_privilege('deermind_app',:table,'DELETE')"),
                            {"table": name},
                        )
                    )
                    if name in {"ai.execution_configs", "ai.ai_candidates"}:
                        self.assertFalse(
                            connection.scalar(
                                text("SELECT has_table_privilege('deermind_app',:table,'UPDATE')"),
                                {"table": name},
                            )
                        )
