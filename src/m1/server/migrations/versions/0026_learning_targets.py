"""Add versioned learning targets."""

from alembic import op

revision = "0026_learning_targets"
down_revision = "0025_activity_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE product.learning_target (
            target_id uuid PRIMARY KEY,
            textbook_id uuid NOT NULL REFERENCES product.textbook(textbook_id),
            head_revision bigint NOT NULL CHECK (head_revision > 0),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE product.learning_target_version (
            target_id uuid NOT NULL REFERENCES product.learning_target(target_id),
            revision bigint NOT NULL CHECK (revision > 0),
            title text NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
            items jsonb NOT NULL,
            chapter_basis jsonb NOT NULL DEFAULT '[]',
            gaps jsonb NOT NULL DEFAULT '[]',
            actor_ref jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY (target_id, revision)
        );
        ALTER TABLE product.learning_target ADD CONSTRAINT current_target_revision
            FOREIGN KEY (target_id, head_revision)
            REFERENCES product.learning_target_version(target_id, revision)
            DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX learning_target_book ON product.learning_target(textbook_id, target_id);
        CREATE INDEX learning_target_event ON product.learning_target(source_event_id);
        CREATE INDEX learning_target_version_event
            ON product.learning_target_version(source_event_id);
        GRANT SELECT, INSERT ON product.learning_target, product.learning_target_version
            TO deermind_app;
        GRANT UPDATE (head_revision, source_event_id) ON product.learning_target TO deermind_app;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE product.learning_target DROP CONSTRAINT current_target_revision;
        DROP TABLE product.learning_target_version, product.learning_target;
    """)
