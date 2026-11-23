"""Keep fixed goal calculations and the current result pointer."""

from alembic import op

revision = "0028_goal_results"
down_revision = "0027_course_adoptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE evaluation.goal_calculation_input (
            input_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            trigger_event_id uuid NOT NULL,
            target_basis_ref uuid NOT NULL,
            adoption_ref uuid NOT NULL,
            mastery_snapshot_ref uuid,
            mastery_publication_seq bigint NOT NULL DEFAULT 0,
            evidence_coverage jsonb NOT NULL,
            calculation_rule_ref text NOT NULL,
            planned_result_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (scope_id, trigger_event_id),
            CHECK (mastery_publication_seq >= 0)
        );
        CREATE TABLE evaluation.goal_evaluation (
            goal_evaluation_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            trigger_event_id uuid NOT NULL,
            input_ref uuid NOT NULL REFERENCES evaluation.goal_calculation_input,
            target_basis_ref uuid NOT NULL,
            result jsonb NOT NULL,
            previous_current_ref uuid REFERENCES evaluation.goal_evaluation,
            current_state_applied boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (scope_id, trigger_event_id)
        );
        CREATE TABLE evaluation.goal_current (
            scope_id uuid PRIMARY KEY,
            current_result_ref uuid REFERENCES evaluation.goal_evaluation,
            target_basis_ref uuid NOT NULL,
            mastery_publication_seq bigint NOT NULL DEFAULT 0
        );
        CREATE INDEX goal_input_event ON evaluation.goal_calculation_input(source_event_id);
        CREATE INDEX goal_result_event ON evaluation.goal_evaluation(source_event_id);
        GRANT SELECT, INSERT ON evaluation.goal_calculation_input, evaluation.goal_evaluation,
            evaluation.goal_current TO deermind_app;
        GRANT UPDATE (current_result_ref, target_basis_ref, mastery_publication_seq)
            ON evaluation.goal_current TO deermind_app;
    """)


def downgrade() -> None:
    op.execute(
        "DROP TABLE evaluation.goal_current, evaluation.goal_evaluation, "
        "evaluation.goal_calculation_input"
    )
