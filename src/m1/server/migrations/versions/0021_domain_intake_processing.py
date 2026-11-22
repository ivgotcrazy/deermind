"""让领域投影器保存待办处理决定，保留历史提交。"""

from alembic import op

revision = "0021_domain_intake_processing"
down_revision = "0020_material_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        GRANT UPDATE (state,revision,result_ref,processed_request_ref,source_event_id)
            ON domain.intake_item TO deermind_app;
    """)


def downgrade() -> None:
    """撤回新增的投影写入权限。"""
    op.execute("""
        REVOKE UPDATE (state,revision,result_ref,processed_request_ref,source_event_id)
            ON domain.intake_item FROM deermind_app;
    """)
