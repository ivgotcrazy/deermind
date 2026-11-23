"""保存学生可确认的题单及其进度。"""

from alembic import op

revision = "0033_detection_plans"
down_revision = "0032_teaching_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE interaction.detection_plans (
            plan_id uuid PRIMARY KEY,
            activity_id uuid NOT NULL,
            scope_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            FOREIGN KEY(scope_id,activity_id)
                REFERENCES interaction.activities(scope_id,activity_id)
        );
        CREATE INDEX detection_plans_scope ON interaction.detection_plans(scope_id,created_at);
        CREATE TABLE interaction.plan_revisions (
            plan_id uuid NOT NULL REFERENCES interaction.detection_plans(plan_id),
            revision bigint NOT NULL CHECK (revision>0),
            adoption_ref uuid NOT NULL,
            purpose text NOT NULL,
            items jsonb NOT NULL CHECK (jsonb_typeof(items)='array'),
            coverage jsonb NOT NULL,
            gaps jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(gaps)='array'),
            feedback_policy jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY(plan_id,revision)
        );
        CREATE TABLE interaction.plan_progress (
            plan_id uuid NOT NULL,
            plan_revision bigint NOT NULL,
            confirmed_by_input uuid REFERENCES interaction.inputs(input_id),
            status text NOT NULL CHECK (status IN (
                'prepared','confirmed','finished','cancelled','superseded'
            )),
            cancelled_items jsonb NOT NULL CHECK (jsonb_typeof(cancelled_items)='array'),
            current_round_ref uuid,
            source_event_id uuid NOT NULL,
            PRIMARY KEY(plan_id,plan_revision),
            FOREIGN KEY(plan_id,plan_revision)
                REFERENCES interaction.plan_revisions(plan_id,revision),
            CHECK (status<>'prepared' OR (confirmed_by_input IS NULL AND current_round_ref IS NULL))
        );
        GRANT UPDATE(confirmed_by_input,status,cancelled_items,current_round_ref,source_event_id)
            ON interaction.plan_progress TO deermind_app;
    """)
    for table in ("detection_plans", "plan_revisions", "plan_progress"):
        op.execute(f"""
            CREATE INDEX interaction_{table}_event ON interaction.{table}(source_event_id);
            GRANT SELECT, INSERT ON interaction.{table} TO deermind_app;
        """)


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
