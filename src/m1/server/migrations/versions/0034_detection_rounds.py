"""正式检测轮在学生确认的题单项上逐轮建立。"""

from alembic import op

revision = "0034_detection_rounds"
down_revision = "0033_detection_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE interaction.detection_rounds (
            round_id uuid PRIMARY KEY,
            activity_id uuid NOT NULL REFERENCES interaction.activities(activity_id),
            plan_id uuid NOT NULL,
            plan_revision bigint NOT NULL,
            item_id text NOT NULL,
            task_use_ref uuid NOT NULL REFERENCES interaction.task_uses(task_use_id),
            opened_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            FOREIGN KEY (plan_id,plan_revision)
                REFERENCES interaction.plan_revisions(plan_id,revision),
            UNIQUE (plan_id,plan_revision,item_id),
            UNIQUE (task_use_ref)
        );
        CREATE TABLE interaction.round_revisions (
            round_id uuid NOT NULL REFERENCES interaction.detection_rounds(round_id),
            revision bigint NOT NULL CHECK (revision>0),
            state text NOT NULL CHECK (state IN ('open','paused','closed')),
            reason text NOT NULL,
            source_input_ref uuid REFERENCES interaction.inputs(input_id),
            source_trigger_ref uuid,
            submission_ref uuid REFERENCES interaction.submissions(submission_id),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY (round_id,revision),
            CHECK (source_input_ref IS NOT NULL OR source_trigger_ref IS NOT NULL)
        );
        ALTER TABLE interaction.task_uses ADD FOREIGN KEY (round_id)
            REFERENCES interaction.detection_rounds(round_id) DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE interaction.submissions ADD FOREIGN KEY (round_id)
            REFERENCES interaction.detection_rounds(round_id);
        ALTER TABLE interaction.plan_progress ADD FOREIGN KEY (current_round_ref)
            REFERENCES interaction.detection_rounds(round_id);
    """)
    for table in ("detection_rounds", "round_revisions"):
        op.execute(f"""
            CREATE INDEX interaction_{table}_event ON interaction.{table}(source_event_id);
            GRANT SELECT, INSERT ON interaction.{table} TO deermind_app;
        """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
