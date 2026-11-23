"""保存求助分类及正式提供两类独立事实。"""

from alembic import op

revision = "0035_detection_help"
down_revision = "0034_detection_rounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE interaction.help_facts (
            help_id uuid NOT NULL,
            stage text NOT NULL CHECK (stage IN ('handled','provided')),
            scope_id uuid NOT NULL,
            source_input_ref uuid NOT NULL REFERENCES interaction.inputs(input_id),
            activity_id uuid NOT NULL REFERENCES interaction.activities(activity_id),
            task_use_id uuid REFERENCES interaction.task_uses(task_use_id),
            classification text NOT NULL
                CHECK (classification IN ('neutral','substantive','uncertain')),
            reason text NOT NULL,
            round_closure_ref jsonb,
            provided_part_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY (help_id,stage),
            CHECK ((stage='handled' AND provided_part_refs='[]'::jsonb)
                OR (stage='provided' AND jsonb_array_length(provided_part_refs)>0))
        );
        CREATE INDEX interaction_help_facts_event ON interaction.help_facts(source_event_id);
        CREATE INDEX interaction_help_facts_scope
            ON interaction.help_facts(scope_id,activity_id,created_at);
        CREATE INDEX interaction_help_facts_task
            ON interaction.help_facts(task_use_id,stage,created_at);
        GRANT SELECT, INSERT ON interaction.help_facts TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
