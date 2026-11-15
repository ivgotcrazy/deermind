"""离线检查凭据保护和随包交付的迁移链。"""

import unittest
from unittest.mock import patch

from deermind.bootstrap.database import DatabaseSettings
from deermind.entrypoints.maintenance.database import migration_config
from pydantic import ValidationError


class DatabaseConfigurationTests(unittest.TestCase):
    def test_no_implicit_connection_target(self) -> None:
        """没有显式配置时不能连接默认数据库。"""
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValidationError):
            DatabaseSettings.from_environment()

    def test_password_is_not_exposed(self) -> None:
        """配置表示与连接串显示隐藏密码，连接仍保留原始值。"""
        password = "special@:/password%42"
        settings = DatabaseSettings.model_validate(
            {
                "host": "localhost",
                "port": 5432,
                "name": "deermind",
                "user": "deermind_app",
                "password": password,
            }
        )
        self.assertNotIn(password, repr(settings))
        self.assertNotIn(password, str(settings.url()))
        self.assertEqual(settings.url().password, password)

    def test_single_migration_head(self) -> None:
        """发布包只能包含与应用要求一致的一个迁移终点。"""
        # 在安装包环境执行时，也能发现迁移脚本漏打包。
        self.assertTrue(migration_config().get_main_option("script_location"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
