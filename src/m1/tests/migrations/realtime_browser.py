"""通过实际 Nginx 和浏览器走查 E01-17。测试进程退出时清理合成数据。"""

import asyncio
import os
import signal
import tempfile
from pathlib import Path
from types import FrameType

import uvicorn
from deermind.entrypoints.api.app import websocket_options
from deermind.entrypoints.maintenance.database import upgrade
from realtime_fixture import RealtimeFixture, environment
from test_database import DatabaseTestCase
from usage_browser import seed


def terminate(_signum: int, _frame: FrameType | None) -> None:
    """Uvicorn 完成关闭后重发 SIGTERM，让 Python 继续执行测试库清理。"""
    raise SystemExit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, terminate)
    fixture = DatabaseTestCase()
    try:
        fixture.setUp()
        upgrade(fixture.migrator)
        asyncio.run(seed(fixture))
        with tempfile.TemporaryDirectory() as root:
            origin = os.environ.get("M1_TEST_WS_BROWSER_ORIGIN", "http://127.0.0.1:5186")
            os.environ.update(environment(fixture.app, Path(root), origin))
            os.environ["M1_AUTH_LOCAL_HTTP"] = str(origin.startswith("http:")).lower()
            application = RealtimeFixture()
            application.drop_next_receipt = True
            uvicorn.run(
                application.transport(),
                host="127.0.0.1",
                port=int(os.environ.get("M1_TEST_WS_BROWSER_PORT", "5187")),
                proxy_headers=False,
                **websocket_options(),
            )
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
