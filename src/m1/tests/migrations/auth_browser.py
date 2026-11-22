"""浏览器走查夹具：随机测试库、合成账号和真实认证API；退出时删除测试库。

仅通过测试环境变量连接数据库，不使用部署业务库。需要先构建clients/dist。
环境准备同test-database.py；本进程仅监听127.0.0.1:5185。
"""

import asyncio
import os
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import uuid4

import uvicorn
from deermind.abstractions.events import ProducerAccess, Ref
from deermind.bootstrap.events import event_store
from deermind.entrypoints.api.app import create_app
from deermind.entrypoints.maintenance.database import upgrade
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.database.connection import application_engine
from deermind.product.accounts.auth import AuthService
from deermind.product.accounts.save import save_initial_account
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from test_database import DatabaseTestCase


async def seed(fixture: DatabaseTestCase) -> None:
    engine = application_engine(fixture.app)
    service = AuthService(engine)
    try:
        for login in ("alpha", "beta"):
            identity = uuid4()
            await save_initial_account(
                engine,
                event_store(),
                ProducerAccess(
                    "product",
                    Ref(owner="runtime", type="service", id="fixture"),
                    frozenset({("account", identity)}),
                ),
                request_id=str(identity),
                account_id=identity,
                login_identifier=login,
                display_name=login,
            )
            with fixture.engine.begin() as connection:
                connection.execute(
                    text("INSERT INTO product.credentials VALUES (:id,:hash,1,now())"),
                    {"id": identity, "hash": service.hasher.hash("test-only-not-a-real-secret")},
                )
    finally:
        await engine.dispose()


def main(
    seed_accounts: Callable[[DatabaseTestCase], Awaitable[None]] = seed,
    *,
    origin: str = "http://127.0.0.1:5185",
    port: int = 5185,
    serve_client: bool = True,
) -> None:
    fixture = DatabaseTestCase()
    try:
        fixture.setUp()
        upgrade(fixture.migrator)
        asyncio.run(seed_accounts(fixture))
        with tempfile.TemporaryDirectory() as directory:
            os.environ.update(
                {
                    "M1_DB_HOST": str(fixture.app.host),
                    "M1_DB_PORT": str(fixture.app.port),
                    "M1_DB_NAME": fixture.name,
                    "M1_DB_USER": "deermind_app",
                    "M1_DB_PASSWORD": str(fixture.app.password),
                    "M1_FILES_ROOT": directory,
                    "M1_FILES_BACKEND": "local",
                    "M1_TEMPORAL_ADDRESS": "127.0.0.1:1",
                    "M1_TEMPORAL_NAMESPACE": "browser-test",
                    "M1_TASK_QUEUE": "unused",
                    "M1_AUTH_LOCAL_HTTP": str(origin.startswith("http:")).lower(),
                    "M1_AUTH_ORIGINS": origin,
                    "M1_AUTH_TRUSTED_PROXIES": "",
                }
            )
            dist = Path(__file__).resolve().parents[2] / "clients/dist"
            app = create_app()
            if serve_client:
                for route in ("admin", "student", "assets"):
                    app.mount("/" + route, StaticFiles(directory=dist / route, html=True))
            configure_logging()
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=port,
                access_log=False,
                log_config=None,
                proxy_headers=False,
            )
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
