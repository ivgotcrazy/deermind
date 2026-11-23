"""按活动追加工作记忆和摘要修订。"""

from alembic import op

revision = "0037_interaction_memory"
down_revision = "0036_teaching_provision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE interaction.memory_revisions (
            memory_id uuid NOT NULL,
            revision bigint NOT NULL CHECK (revision>0),
            scope_id uuid NOT NULL,
            activity_id uuid NOT NULL REFERENCES interaction.activities(activity_id),
            kind text NOT NULL CHECK (kind IN ('entries','summary')),
            basis_message_seq bigint NOT NULL CHECK (basis_message_seq>=0),
            content jsonb NOT NULL,
            source_ref jsonb NOT NULL,
            previous_ref jsonb,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY (memory_id,revision)
        );
        CREATE TABLE interaction.memory_heads (
            scope_id uuid NOT NULL,
            activity_id uuid NOT NULL REFERENCES interaction.activities(activity_id),
            kind text NOT NULL CHECK (kind IN ('entries','summary')),
            memory_id uuid NOT NULL,
            revision bigint NOT NULL,
            PRIMARY KEY (scope_id,activity_id,kind),
            FOREIGN KEY (memory_id,revision)
                REFERENCES interaction.memory_revisions(memory_id,revision)
        );
        CREATE INDEX interaction_memory_revisions_event
            ON interaction.memory_revisions(source_event_id);
        GRANT SELECT, INSERT ON interaction.memory_revisions TO deermind_app;
        GRANT SELECT, INSERT, UPDATE ON interaction.memory_heads TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
