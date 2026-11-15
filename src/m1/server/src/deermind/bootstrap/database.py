"""独立读取数据库配置，不要求迁移命令具备Temporal和文件配置。"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from deermind.infrastructure.database.connection import application_engine, check_database
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseSettings(BaseModel):
    """显式提供数据库位置和凭据；密码不出现在命令参数或对象表示中。"""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    user: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)

    def url(self) -> URL:
        """由URL.create处理密码中的特殊字符，避免手动拼接连接串。"""
        return URL.create(
            "postgresql+psycopg",
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
        )

    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        """拒绝缺少的配置，不记录环境变量或密码。"""
        values = {
            name: os.environ[f"M1_DB_{name.upper()}"]
            for name in cls.model_fields
            if f"M1_DB_{name.upper()}" in os.environ
        }
        return cls.model_validate(values)


@asynccontextmanager
async def database_lifespan() -> AsyncGenerator[AsyncEngine]:
    """受理工作前检查数据库；启动失败或退出时均释放本进程连接池。"""
    engine = application_engine(DatabaseSettings.from_environment().url())
    try:
        await check_database(engine)
        yield engine
    finally:
        await engine.dispose()
