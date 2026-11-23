"""装配领域定义使用的事件和文件存储。"""

from pathlib import Path
from typing import Literal

from deermind.bootstrap.events import event_reader, event_store
from deermind.bootstrap.settings import Settings
from deermind.bootstrap.supply_operation import supply_config
from deermind.foundation.system.events.attachments import FactAttachments
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore
from deermind.infrastructure.files.local import LocalFiles
from deermind.spaces.domain.definitions import DomainDefinitions
from deermind.spaces.domain.public import DomainService
from deermind.spaces.domain.supply import TaskSupply
from deermind.spaces.domain.supply_generation import GenerateSupply
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


def configure_task_supply(
    engine: AsyncEngine,
    events: EventStore,
    reader: EventReader,
    attachments: FactAttachments,
    settings: Settings,
) -> tuple[TaskSupply, GenerateSupply]:
    generation = GenerateSupply(engine, events, attachments, settings.task_queue, supply_config())
    return TaskSupply(events, reader, generation), generation
