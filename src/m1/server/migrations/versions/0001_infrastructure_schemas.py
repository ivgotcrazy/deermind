"""建立模块schema；业务表随所属增量建立。

迁移账号负责DDL；应用只读取迁移版本、使用模块schema。
后续迁移逐表授予所需权限，不提前开放所有未来表。
"""

from alembic import op

revision = "0001_infrastructure_schemas"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """创建模块schema并授予最小访问权限，由外层事务保证原子性。"""
    # 已有但来源不明的对象必须报错，不能静默接管。
    for schema in ("product", "domain", "interaction", "evaluation", "runtime", "ai"):
        op.execute(f'CREATE SCHEMA "{schema}" AUTHORIZATION deermind_migrator')
        op.execute(f'REVOKE ALL ON SCHEMA "{schema}" FROM PUBLIC')
        op.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO deermind_app')

    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute("GRANT USAGE ON SCHEMA public TO deermind_app")
    op.execute("REVOKE ALL ON public.alembic_version FROM PUBLIC, deermind_app")
    op.execute("GRANT SELECT ON public.alembic_version TO deermind_app")


def downgrade() -> None:
    """拒绝自动删除结构；变更应另写经审阅的向前迁移。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
