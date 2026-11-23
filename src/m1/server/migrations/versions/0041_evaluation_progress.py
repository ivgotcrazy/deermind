"""Track the active evaluation source for each learning space."""

from alembic import op

revision = "0041_evaluation_progress"
down_revision = "0040_evaluation_mastery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE evaluation.evaluation_progress (
            scope_id uuid PRIMARY KEY,
            scanned_through_seq bigint NOT NULL DEFAULT 0 CHECK (scanned_through_seq >= 0),
            active_trigger_event_id uuid,
            active_source_seq bigint,
            CHECK ((active_trigger_event_id IS NULL) = (active_source_seq IS NULL)),
            CHECK (active_source_seq IS NULL OR active_source_seq > scanned_through_seq)
        );
        -- Earlier development increments exercised interpretation without applying it.
        -- Evaluation sequencing starts with new events after this migration.
        INSERT INTO evaluation.evaluation_progress (scope_id, scanned_through_seq)
        SELECT scope_id, last_seq FROM runtime.scope_event_heads
        WHERE scope_kind='learning_space';
        GRANT SELECT, INSERT, UPDATE ON evaluation.evaluation_progress TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
