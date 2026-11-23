"""按触发事件保存固定的评价输入。"""

from alembic import op

revision = "0038_evaluation_input"
down_revision = "0037_interaction_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE evaluation.evaluation_input (
            input_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            trigger_event_id uuid NOT NULL,
            source_seq bigint NOT NULL CHECK (source_seq>0),
            source_kind text NOT NULL CHECK (source_kind IN ('answer','teaching')),
            source_id uuid NOT NULL,
            input jsonb NOT NULL CHECK (jsonb_typeof(input)='object'),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (scope_id,trigger_event_id)
        );
        CREATE INDEX evaluation_input_source ON evaluation.evaluation_input(source_event_id);
        GRANT SELECT, INSERT ON evaluation.evaluation_input TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
