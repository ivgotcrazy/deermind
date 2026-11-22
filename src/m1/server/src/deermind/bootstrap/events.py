"""汇总已实施事件格式；尚未实现的登记不会被静默接受。"""

from deermind.abstractions.files import FileStorage
from deermind.bootstrap.messaging import subscriptions
from deermind.foundation.ai.facts import REGISTRATIONS as AI_REGISTRATIONS
from deermind.foundation.system.delivery.facts import DELIVERY_REGISTRATION
from deermind.foundation.system.delivery.outbox import Outbox
from deermind.foundation.system.events.query import EventReader
from deermind.foundation.system.events.store import EventStore
from deermind.foundation.system.executions.facts import (
    EXECUTION_REGISTRATION,
)
from deermind.foundation.system.files.records import FILE_REGISTRATION
from deermind.foundation.system.projections.contracts import REBUILD_FINISHED
from deermind.foundation.system.waits.facts import REGISTRATION as WAIT_REGISTRATION
from deermind.product.accounts.auth_facts import SIGNED_IN, SIGNED_OUT
from deermind.product.accounts.facts import ACCOUNT_REGISTRATION
from deermind.product.accounts.recovery_facts import RECOVERED
from deermind.product.accounts.usage_events import (
    USAGE_CONFIRMED,
)
from sqlalchemy.ext.asyncio import AsyncEngine

REGISTRATIONS = [
    ACCOUNT_REGISTRATION,
    FILE_REGISTRATION,
    REBUILD_FINISHED,
    SIGNED_IN,
    SIGNED_OUT,
    USAGE_CONFIRMED,
    RECOVERED,
    DELIVERY_REGISTRATION,
    EXECUTION_REGISTRATION,
    WAIT_REGISTRATION,
    *AI_REGISTRATIONS,
]


def event_store() -> EventStore:
    return EventStore(REGISTRATIONS, arrange_delivery=Outbox(subscriptions()).arrange)


def event_reader(engine: AsyncEngine, files: FileStorage) -> EventReader:
    return EventReader(engine, files, REGISTRATIONS)
