"""重建白名单只含已实现的账号查询投影；文件及运行控制不进入替换集合。"""

import hashlib
import secrets
from pathlib import Path

from deermind.bootstrap.events import event_reader
from deermind.foundation.system.events import contracts, query, reading, store
from deermind.foundation.system.events.contracts import StoredEvent
from deermind.foundation.system.files.ports import FileStorage
from deermind.foundation.system.projections import contracts as projection_contracts
from deermind.foundation.system.projections import rebuild
from deermind.foundation.system.projections.contracts import RebuildSpec
from deermind.foundation.system.projections.rebuild import ProjectionRebuilder
from deermind.product.accounts import auth_facts, facts
from sqlalchemy.ext.asyncio import AsyncEngine


def account_rebuilder(engine: AsyncEngine, files: FileStorage) -> ProjectionRebuilder:
    """固定转换和校验代码的摘要；代码变化后不能继续旧副本。"""
    digest = hashlib.sha256(Path(__file__).read_bytes())
    for module in (
        facts,
        auth_facts,
        contracts,
        query,
        reading,
        store,
        projection_contracts,
        rebuild,
    ):
        if module.__file__ is None:
            raise RuntimeError("Rebuild implementation is not available for verification")
        digest.update(module.__name__.encode())
        digest.update(Path(module.__file__).read_bytes())
    spec = RebuildSpec(
        projector_id=facts.ACCOUNT_REGISTRATION.projector_id,
        scope_kind="account",
        target="product.accounts",
        key="account_id",
        columns=(
            "account_id",
            "login_identifier",
            "display_name",
            "role",
            "status",
            "revision",
            "created_at",
            "source_event_id",
        ),
        implementation_digest=digest.hexdigest(),
        values=account_projection,
    )
    # 维护读取不产生列表游标；此密钥不用于任何浏览器分页。
    reader = event_reader(engine, files, cursor_key=secrets.token_bytes(32))
    return ProjectionRebuilder(engine, reader, spec)


def account_projection(event: StoredEvent) -> dict[str, object] | None:
    """审计事实已由登记Schema校验，不从历史登录恢复有效会话。"""
    if event.draft.event_type in {"AccountSignedIn", "AccountSignedOut"}:
        return None
    return facts.account_values(event)
