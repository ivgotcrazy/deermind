"""装配账号服务，网页和管理命令复用同一事务实现。"""

from pathlib import Path

from deermind.bootstrap.events import event_reader, event_store
from deermind.infrastructure.files.local import LocalFiles
from deermind.product.accounts.auth import AuthService
from deermind.product.accounts.manage import AccountManager
from deermind.product.accounts.usage import AccountUsage
from deermind.product.public.usage import UsageService
from sqlalchemy.ext.asyncio import AsyncEngine


def configure_usage(engine: AsyncEngine, root: Path) -> UsageService:
    return AccountUsage(
        engine,
        event_store(),
        event_reader(engine, LocalFiles(root, backend="local")),
    )


async def configure_account_management(engine: AsyncEngine) -> tuple[AccountManager, AuthService]:
    auth = AuthService(engine)
    await auth.initialize()
    return AccountManager(engine, auth, event_store()), auth
