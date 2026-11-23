"""保存每份固定评价输入的经核对解释。"""

from alembic import op

revision = "0039_evaluation_interpretation"
down_revision = "0038_evaluation_input"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE evaluation.interpretation (
            interpretation_id uuid PRIMARY KEY,
            input_ref uuid NOT NULL UNIQUE REFERENCES evaluation.evaluation_input(input_id),
            ai_call_ref jsonb NOT NULL,
            contract_ref jsonb NOT NULL,
            candidate jsonb NOT NULL CHECK (jsonb_typeof(candidate)='object'),
            validation jsonb NOT NULL CHECK (jsonb_typeof(validation)='array'),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE INDEX evaluation_interpretation_source ON evaluation.interpretation(source_event_id);
        GRANT SELECT, INSERT ON evaluation.interpretation TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
