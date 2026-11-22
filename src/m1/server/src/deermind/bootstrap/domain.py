"""装配领域定义使用的事件和文件存储。"""

from pathlib import Path
from typing import Literal

from deermind.bootstrap.events import event_reader, event_store
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.infrastructure.files.local import LocalFiles
from deermind.spaces.domain.definitions import DomainDefinitions
from deermind.spaces.domain.public import DomainService
from sqlalchemy.ext.asyncio import AsyncEngine


def configure_domain(
    engine: AsyncEngine, root: Path, *, backend: Literal["local", "pvc"]
) -> DomainService:
    files = LocalFiles(root, backend=backend)
    return DomainDefinitions(
        engine,
        event_store(),
        event_reader(engine, files),
        FactAttachments(engine, files),
    )
