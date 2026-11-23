"""保存讲解节点实际取材，以及程序对候选的采用或拒绝。"""

from alembic import op

revision = "0030_teaching_decisions"
down_revision = "0029_activity_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE interaction.context_bundles (
            bundle_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            run_ref uuid NOT NULL,
            source_ref jsonb NOT NULL,
            purpose text NOT NULL,
            activity_revision_ref jsonb,
            adoption_ref uuid NOT NULL,
            config_ref uuid NOT NULL REFERENCES interaction.resolved_configs(config_id),
            materials jsonb NOT NULL,
            memory_refs jsonb NOT NULL DEFAULT '[]',
            publication_refs jsonb NOT NULL DEFAULT '[]',
            omissions jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE INDEX context_bundle_source ON interaction.context_bundles(source_event_id);
        CREATE TABLE interaction.decision_records (
            decision_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            input_ref uuid REFERENCES interaction.inputs(input_id),
            source_trigger_ref uuid,
            activity_revision_ref jsonb,
            context_bundle_id uuid NOT NULL REFERENCES interaction.context_bundles(bundle_id),
            ai_candidate_ref jsonb,
            proposal jsonb NOT NULL,
            validation jsonb NOT NULL,
            accepted_action jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            CHECK (input_ref IS NOT NULL OR source_trigger_ref IS NOT NULL)
        );
        CREATE INDEX decision_source ON interaction.decision_records(source_event_id);
        GRANT SELECT, INSERT ON interaction.context_bundles, interaction.decision_records
            TO deermind_app;
    """)


def downgrade() -> None:
    op.drop_table("decision_records", schema="interaction")
    op.drop_table("context_bundles", schema="interaction")
