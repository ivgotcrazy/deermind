"""汇总已实施事件及投影；尚未实现的登记不会被静默接受。"""

from deermind.foundation.system.events.store import EventStore
from deermind.product.accounts.facts import ACCOUNT_REGISTRATION


def event_store() -> EventStore:
    return EventStore([ACCOUNT_REGISTRATION])
