"""装配账号业务维护入口；不定义转换规则或业务表结构。"""

import hashlib
from pathlib import Path

from deermind.abstractions import event_reading as reading
from deermind.abstractions import events as contracts
from deermind.abstractions.files import FileStorage
from deermind.bootstrap.events import event_reader
from deermind.foundation.system.events import query, store
from deermind.foundation.system.projections import contracts as maintenance_contracts
from deermind.foundation.system.projections import receipts, records
from deermind.infrastructure.database.connection import EXPECTED_REVISION, MAINTENANCE_LOCK
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
    """记录本批实现摘要；副本和表范围由账号业务维护。"""
    digest = hashlib.sha256(Path(__file__).read_bytes())
    # 把重建链路涉及的各模块名称与源码计入摘要，版本不符即拒绝重建。
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
            # 内置/打包模块取不到源码，无法参与实现摘要校验。
            raise RuntimeError("Rebuild implementation is not available for verification")
        digest.update(module.__name__.encode())
        digest.update(Path(module.__file__).read_bytes())
    reader = event_reader(engine, files)
    maintenance = records.ProjectionRecords(
        engine, expected_revision=EXPECTED_REVISION, maintenance_lock=MAINTENANCE_LOCK
    )
    return AccountRebuilder(reader, AccountRebuildSpec(digest.hexdigest()), maintenance)
