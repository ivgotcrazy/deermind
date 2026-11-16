"""汇总已实施事件及投影；尚未实现的登记不会被静默接受。"""

from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.reading import ReadHandler
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.files.ports import FileStorage
from deermind.foundation.system.projections.contracts import REBUILD_FINISHED
from deermind.infrastructure.files.records import FILE_READ_POLICY, FILE_REGISTRATION
from deermind.product.accounts.auth_facts import AUTH_READ_POLICIES, SIGNED_IN, SIGNED_OUT
from deermind.product.accounts.facts import ACCOUNT_READ_POLICY, ACCOUNT_REGISTRATION
from sqlalchemy.ext.asyncio import AsyncEngine


def event_store() -> EventStore:
    return EventStore(
        [ACCOUNT_REGISTRATION, FILE_REGISTRATION, REBUILD_FINISHED, SIGNED_IN, SIGNED_OUT]
    )


def event_reader(engine: AsyncEngine, files: FileStorage, *, cursor_key: bytes) -> EventReader:
    """只装配已实现Schema的维护读取；登录和业务页面落地时再登记各自字段许可。"""
    return EventReader(
        engine,
        files,
        [ACCOUNT_REGISTRATION, FILE_REGISTRATION, REBUILD_FINISHED, SIGNED_IN, SIGNED_OUT],
        [
            ReadHandler("runtime.projection_read", "runtime", "projection_rebuild"),
            ReadHandler("runtime.file_review", "runtime", "execution_support"),
        ],
        [ACCOUNT_READ_POLICY, FILE_READ_POLICY, *AUTH_READ_POLICIES],
        cursor_key=cursor_key,
    )
