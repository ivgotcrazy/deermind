"""在调用方已加锁的事务中执行唯一业务迁移链。"""

from alembic import context
from sqlalchemy.engine import Connection

connection = context.config.attributes.get("connection")
if not isinstance(connection, Connection):
    raise RuntimeError("Use deermind-database upgrade; an explicit locked connection is required")

context.configure(connection=connection, version_table_schema="public")
with context.begin_transaction():
    context.run_migrations()
