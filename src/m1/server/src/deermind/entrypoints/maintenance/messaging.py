"""以显式环境配置和维护凭据初始化消息资源；不删除或覆盖既有资源。"""

import argparse
import asyncio
from uuid import UUID

from deermind.bootstrap.database import DatabaseSettings
from deermind.bootstrap.messaging import subscriptions
from deermind.foundation.system.delivery.contracts import specifications
from deermind.foundation.system.delivery.recovery import redeliver
from deermind.foundation.system.logging import configure_logging
from deermind.infrastructure.nats.connection import MessagingSettings, connect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


async def initialize() -> None:
    async with connect(MessagingSettings.from_environment()) as transport:
        await transport.initialize(specifications(subscriptions()))


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Initialize messaging or explicitly redeliver one event"
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("initialize")
    recovery = subparsers.add_parser("redeliver")
    recovery.add_argument("--handoff", required=True, type=UUID)
    recovery.add_argument("--operator", required=True)
    recovery.add_argument("--authorization", required=True)
    args = parser.parse_args()
    if args.action == "initialize":
        asyncio.run(initialize())
    else:
        asyncio.run(recover(args.handoff, args.operator, args.authorization))


async def recover(handoff: UUID, operator: str, authorization: str) -> None:
    engine = create_async_engine(
        DatabaseSettings.from_environment().url(),
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=10000 -c lock_timeout=3000 "
            "-c idle_in_transaction_session_timeout=10000",
        },
    )
    try:
        identity = await redeliver(engine, handoff, operator=operator, authorization=authorization)
        print(f"Redelivery arranged: {identity}")
    finally:
        await engine.dispose()
