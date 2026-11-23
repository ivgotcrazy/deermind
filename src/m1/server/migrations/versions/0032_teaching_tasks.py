"""保存正式呈现的教学题目和学生实际作答。"""

from alembic import op

revision = "0032_teaching_tasks"
down_revision = "0031_task_supply"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE interaction.task_uses (
            task_use_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            activity_id uuid NOT NULL,
            round_id uuid,
            plan_item_ref jsonb,
            instance_ref jsonb,
            statement jsonb NOT NULL,
            adoption_ref uuid NOT NULL,
            purpose text NOT NULL CHECK (purpose IN (
                'example','practice','detection','student_question'
            )),
            method_conditions jsonb NOT NULL,
            prepared_at timestamptz NOT NULL,
            provided_message_ref uuid NOT NULL REFERENCES interaction.messages(message_id),
            source_event_id uuid NOT NULL,
            FOREIGN KEY (scope_id, activity_id)
                REFERENCES interaction.activities(scope_id, activity_id),
            CHECK ((purpose='detection') = (round_id IS NOT NULL)),
            CHECK ((purpose='detection') = (plan_item_ref IS NOT NULL))
        );
        CREATE TABLE interaction.submissions (
            submission_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            source_input_ref uuid NOT NULL REFERENCES interaction.inputs(input_id),
            task_use_ref uuid NOT NULL REFERENCES interaction.task_uses(task_use_id),
            activity_id uuid NOT NULL,
            round_id uuid,
            answer jsonb NOT NULL,
            help_basis jsonb NOT NULL,
            adoption_ref uuid NOT NULL,
            accepted_at timestamptz NOT NULL,
            event_ref uuid NOT NULL,
            source_event_id uuid NOT NULL,
            FOREIGN KEY (scope_id, activity_id)
                REFERENCES interaction.activities(scope_id, activity_id),
            UNIQUE (source_input_ref, task_use_ref),
            CHECK (event_ref=source_event_id)
        );
        CREATE TABLE interaction.answer_feedback (
            feedback_id uuid PRIMARY KEY,
            submission_id uuid NOT NULL REFERENCES interaction.submissions(submission_id),
            verdict text NOT NULL CHECK (verdict IN ('correct','incorrect','partial','uncertain')),
            basis_refs jsonb NOT NULL DEFAULT '[]',
            feedback jsonb NOT NULL,
            limitations jsonb NOT NULL,
            run_ref uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (submission_id, run_ref)
        );
        CREATE UNIQUE INDEX submissions_round ON interaction.submissions(round_id)
            WHERE round_id IS NOT NULL;
        CREATE INDEX submissions_task_use
            ON interaction.submissions(scope_id,task_use_ref,accepted_at);
        CREATE INDEX task_uses_scope ON interaction.task_uses(scope_id,prepared_at);
    """)
    for table in ("task_uses", "submissions", "answer_feedback"):
        op.execute(f"""
            CREATE INDEX interaction_{table}_event ON interaction.{table}(source_event_id);
            GRANT SELECT, INSERT ON interaction.{table} TO deermind_app;
        """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
