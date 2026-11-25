"""Index immutable course versions and the student's last entered space."""

from alembic import op

revision = "0042_fixed_space_course"
down_revision = "0041_evaluation_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE product.course_application ADD COLUMN revision bigint;
        WITH RECURSIVE versions AS (
            SELECT application_id, 1::bigint AS revision
            FROM product.course_application WHERE previous_application_id IS NULL
            UNION ALL
            SELECT c.application_id, v.revision + 1
            FROM versions v JOIN product.course_application c
                ON c.previous_application_id = v.application_id
        )
        UPDATE product.course_application c SET revision=v.revision
        FROM versions v WHERE c.application_id=v.application_id;
        ALTER TABLE product.course_application
            ALTER COLUMN revision SET NOT NULL,
            ADD CONSTRAINT course_application_revision_positive CHECK (revision > 0),
            ADD CONSTRAINT course_application_revision_unique
                UNIQUE (textbook_id, target_id, revision);

        ALTER TABLE product.learning_space
            ADD COLUMN application_ref uuid REFERENCES product.course_application,
            ADD COLUMN last_entered_at timestamptz;
        UPDATE product.learning_space s SET application_ref=a.application_ref
        FROM product.space_adoption a WHERE a.adoption_id=s.current_adoption_ref;

        WITH last_entry AS (
            SELECT scope_id, max(recorded_at) AS recorded_at FROM runtime.events
            WHERE scope_kind='learning_space' AND event_type='LearningSpaceEntered'
                AND producer='product'
            GROUP BY scope_id
        )
        UPDATE product.learning_space s SET last_entered_at=e.recorded_at
        FROM last_entry e WHERE e.scope_id=s.space_id;

        -- Finish checking the backfilled rows before altering the populated table.
        SET CONSTRAINTS ALL IMMEDIATE;
        ALTER TABLE product.learning_space ALTER COLUMN application_ref SET NOT NULL;
        ALTER TABLE product.learning_space DROP CONSTRAINT
            learning_space_student_id_textbook_id_target_id_key;
        ALTER TABLE product.learning_space ADD CONSTRAINT learning_space_version_unique
            UNIQUE(student_id, application_ref);
        CREATE INDEX space_student_recent ON product.learning_space
            (student_id, last_entered_at DESC NULLS LAST, space_id);
        GRANT UPDATE (application_ref, last_entered_at) ON product.learning_space TO deermind_app;
    """)


def downgrade() -> None:
    # Restoring the old key after opening two versions would discard a real space.
    # Adding it first fails atomically when any such spaces exist.
    op.execute("""
        ALTER TABLE product.learning_space ADD CONSTRAINT
            learning_space_student_id_textbook_id_target_id_key
            UNIQUE (student_id, textbook_id, target_id);
        DROP INDEX product.space_student_recent;
        ALTER TABLE product.learning_space
            DROP CONSTRAINT learning_space_version_unique,
            DROP COLUMN last_entered_at, DROP COLUMN application_ref;
        ALTER TABLE product.course_application DROP COLUMN revision;
    """)
