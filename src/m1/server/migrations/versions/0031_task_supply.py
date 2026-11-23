"""建立 Domain 供题结果和同一触发只处理一次的约束。"""

from alembic import op

revision = "0031_task_supply"
down_revision = "0030_teaching_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE domain.supply_batch (
            batch_id uuid PRIMARY KEY,
            trigger_event_id uuid NOT NULL UNIQUE,
            scope_id uuid NOT NULL,
            input_artifact_id uuid NOT NULL REFERENCES domain.artifact(artifact_id),
            items jsonb NOT NULL,
            unfilled jsonb NOT NULL,
            completed_event_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            CHECK (completed_event_id = source_event_id)
        );
        CREATE INDEX supply_batch_scope ON domain.supply_batch(scope_id,batch_id);
        CREATE INDEX supply_batch_source ON domain.supply_batch(source_event_id);
        GRANT SELECT, INSERT ON domain.supply_batch TO deermind_app;
    """)


def downgrade() -> None:
    op.drop_table("supply_batch", schema="domain")
