"""允许追加候选批的替代决定，保留不可变候选正文。"""

from alembic import op

revision = "0018_material_corrections"
down_revision = "0017_material_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "GRANT UPDATE (decision_state,decision_revision,source_event_id) "
        "ON product.material_candidate_batch TO deermind_app"
    )


def downgrade() -> None:
    """候选历史仅通过前向迁移维护。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
