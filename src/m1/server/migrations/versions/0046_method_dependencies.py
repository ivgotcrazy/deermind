"""Index task knowledge and method prerequisites alongside immutable earlier editions."""

from alembic import op

revision = "0046_method_dependencies"
down_revision = "0045_edition_owned_members"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE domain.object_reference DROP CONSTRAINT object_reference_relation_kind_check,
        ADD CHECK (relation_kind IN (
            'task_method','task_prerequisite','prerequisite_method_scope','solution_kc',
            'instance_task','reference_solution','task_knowledge','method_prerequisite'
        ))
    """)


def downgrade() -> None:
    raise RuntimeError("Use a forward migration for published definitions")
