"""保存教学机会和独立的浏览器呈现记录。"""

from alembic import op

revision = "0036_teaching_provision"
down_revision = "0035_detection_help"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE interaction.teaching_opportunities (
            opportunity_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            activity_id uuid NOT NULL REFERENCES interaction.activities(activity_id),
            adoption_ref uuid NOT NULL,
            purpose text NOT NULL,
            opened_by_input uuid REFERENCES interaction.inputs(input_id),
            source_trigger_ref uuid,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            CHECK (opened_by_input IS NOT NULL OR source_trigger_ref IS NOT NULL)
        );
        CREATE TABLE interaction.opportunity_closures (
            opportunity_id uuid PRIMARY KEY
                REFERENCES interaction.teaching_opportunities(opportunity_id),
            provided_part_refs jsonb NOT NULL,
            purpose text NOT NULL,
            close_reason text NOT NULL CHECK (
                close_reason IN ('completed','interrupted','cancelled','unable_to_continue')
            ),
            closed_at timestamptz NOT NULL,
            source_input_ref uuid REFERENCES interaction.inputs(input_id),
            source_trigger_ref uuid,
            event_ref uuid NOT NULL UNIQUE,
            source_event_id uuid NOT NULL,
            CHECK (source_input_ref IS NOT NULL OR source_trigger_ref IS NOT NULL),
            CHECK (jsonb_array_length(provided_part_refs)>0)
        );
        CREATE TABLE interaction.presentations (
            presentation_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            surface text NOT NULL CHECK (surface IN ('chat','history','textbook')),
            resource_ref jsonb NOT NULL,
            part_refs jsonb NOT NULL,
            received_at timestamptz NOT NULL,
            client_reported_at timestamptz,
            source_event_id uuid NOT NULL
        );
        CREATE INDEX interaction_opportunities_scope
            ON interaction.teaching_opportunities(scope_id,activity_id,created_at);
        CREATE INDEX interaction_presentations_scope
            ON interaction.presentations(scope_id,received_at);
    """)
    for table in ("teaching_opportunities", "opportunity_closures", "presentations"):
        op.execute(f"""
            CREATE INDEX interaction_{table}_event ON interaction.{table}(source_event_id);
            GRANT SELECT, INSERT ON interaction.{table} TO deermind_app;
        """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
