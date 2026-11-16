"""装配账号业务维护入口；不定义转换规则或业务表结构。"""

import hashlib
import secrets
from pathlib import Path

from deermind.bootstrap.events import event_reader
from deermind.foundation.system.events import contracts, query, reading, store
from deermind.foundation.system.files.ports import FileStorage
from deermind.foundation.system.projections import contracts as maintenance_contracts
from deermind.foundation.system.projections import receipts, records
from deermind.product.accounts import (
    auth_facts,
    facts,
    projections,
    rebuild,
    recovery_facts,
    usage_events,
    usage_facts,
)
from deermind.product.accounts.rebuild import AccountRebuilder, AccountRebuildSpec
from sqlalchemy.ext.asyncio import AsyncEngine


def account_rebuilder(engine: AsyncEngine, files: FileStorage) -> AccountRebuilder:
    """实现变化不能续用旧副本；副本和表范围由账号业务维护。"""
    digest = hashlib.sha256(Path(__file__).read_bytes())
    for module in (
        facts,
        auth_facts,
        usage_events,
        usage_facts,
        recovery_facts,
        projections,
        rebuild,
        contracts,
        query,
        reading,
        store,
        maintenance_contracts,
        receipts,
        records,
    ):
        if module.__file__ is None:
            raise RuntimeError("Rebuild implementation is not available for verification")
        digest.update(module.__name__.encode())
        digest.update(Path(module.__file__).read_bytes())
    reader = event_reader(engine, files, cursor_key=secrets.token_bytes(32))
    return AccountRebuilder(engine, reader, AccountRebuildSpec(digest.hexdigest()))
