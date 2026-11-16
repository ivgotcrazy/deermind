"""登记业务拥有的多表维护副本；旧记录及旧完成事实保持原样。"""

from alembic import op

revision = "0009_projection_ownership"
down_revision = "0008_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """空映射表示旧单表维护记录，不能作为新业务重建的续做输入。"""
    op.execute("""
        ALTER TABLE runtime.projection_rebuilds
        ADD COLUMN target_relations jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(target_relations)='object')
    """)


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration; preserve maintenance records")
