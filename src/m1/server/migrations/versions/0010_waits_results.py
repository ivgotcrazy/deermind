"""结果登记、等待和接续收据；条件与决议分开保存，不创建业务订阅。"""

from alembic import op

revision = "0010_waits_results"
down_revision = "0009_projection_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """结果只追加，等待只修改决议；禁止应用删除历史或改写条件。"""
    op.execute("""
        CREATE TABLE runtime.expected_results (
            scope_id uuid NOT NULL,
            trigger_event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            producer text NOT NULL,
            result_kind text NOT NULL,
            execution_id uuid NOT NULL REFERENCES runtime.executions(execution_id),
            accepted_at timestamptz NOT NULL,
            PRIMARY KEY (scope_id,trigger_event_id,producer,result_kind),
            UNIQUE (scope_id,trigger_event_id,producer,result_kind,execution_id)
        );
        CREATE TABLE runtime.result_attempts (
            scope_id uuid NOT NULL,
            trigger_event_id uuid NOT NULL,
            producer text NOT NULL,
            result_kind text NOT NULL,
            attempt_id uuid NOT NULL REFERENCES runtime.execution_attempts(attempt_id),
            outcome text NOT NULL CHECK (outcome IN ('pending','completed','failed','cancelled')),
            failure_ref jsonb,
            created_at timestamptz NOT NULL,
            finished_at timestamptz,
            PRIMARY KEY (scope_id,trigger_event_id,producer,result_kind,attempt_id),
            FOREIGN KEY (scope_id,trigger_event_id,producer,result_kind)
                REFERENCES runtime.expected_results(scope_id,trigger_event_id,producer,result_kind),
            CHECK ((outcome='pending') = (finished_at IS NULL))
        );
        CREATE TABLE runtime.published_results (
            scope_id uuid NOT NULL,
            trigger_event_id uuid NOT NULL,
            producer text NOT NULL,
            result_kind text NOT NULL,
            execution_id uuid NOT NULL,
            attempt_id uuid NOT NULL,
            result_ref jsonb NOT NULL,
            publication_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(publication_refs)='array'),
            payload jsonb NOT NULL,
            event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            published_at timestamptz NOT NULL,
            PRIMARY KEY (scope_id,trigger_event_id,producer,result_kind),
            FOREIGN KEY (scope_id,trigger_event_id,producer,result_kind,execution_id)
                REFERENCES runtime.expected_results
                    (scope_id,trigger_event_id,producer,result_kind,execution_id),
            FOREIGN KEY (execution_id,attempt_id)
                REFERENCES runtime.execution_attempts(execution_id,attempt_id),
            FOREIGN KEY (scope_id,trigger_event_id,producer,result_kind,attempt_id)
                REFERENCES runtime.result_attempts
                    (scope_id,trigger_event_id,producer,result_kind,attempt_id)
        );
        CREATE TABLE runtime.waits (
            wait_id uuid PRIMARY KEY,
            owner_ref jsonb NOT NULL,
            execution_id uuid NOT NULL REFERENCES runtime.executions(execution_id),
            step_key text NOT NULL,
            condition jsonb NOT NULL,
            condition_hash text NOT NULL CHECK (condition_hash ~ '^[0-9a-f]{64}$'),
            probe_ref jsonb NOT NULL,
            deadline_at timestamptz NOT NULL,
            resume_action_id uuid NOT NULL UNIQUE,
            on_match text NOT NULL,
            on_timeout text NOT NULL,
            resolution text NOT NULL CHECK
                (resolution IN ('pending','matched','timed_out','cancelled')),
            matched_event_ref uuid REFERENCES runtime.events(event_id),
            result_ref jsonb,
            created_at timestamptz NOT NULL,
            resolved_at timestamptz,
            UNIQUE (execution_id,step_key,condition_hash),
            UNIQUE (wait_id,resume_action_id),
            CHECK (deadline_at>created_at),
            CHECK ((resolution='pending') = (resolved_at IS NULL)),
            CHECK ((resolution='matched') = (matched_event_ref IS NOT NULL))
        );
        CREATE TABLE runtime.wait_handling (
            wait_id uuid PRIMARY KEY,
            resume_action_id uuid NOT NULL UNIQUE,
            state text NOT NULL CHECK (state IN ('awaiting','committed','failed','cancelled')),
            handling_receipt_ref jsonb,
            failure_ref jsonb,
            updated_at timestamptz NOT NULL,
            FOREIGN KEY (wait_id,resume_action_id)
                REFERENCES runtime.waits(wait_id,resume_action_id),
            CHECK ((state='committed') = (handling_receipt_ref IS NOT NULL)),
            CHECK ((state='failed') = (failure_ref IS NOT NULL))
        );
        CREATE INDEX ix_expected_execution ON runtime.expected_results(execution_id);
        CREATE INDEX ix_waits_due ON runtime.waits(resolution,deadline_at);
        CREATE INDEX ix_waits_execution ON runtime.waits(execution_id,resolution);
        GRANT SELECT,INSERT ON runtime.expected_results,runtime.result_attempts,
            runtime.published_results,runtime.waits,runtime.wait_handling TO deermind_app;
        GRANT UPDATE(outcome,failure_ref,finished_at)
            ON runtime.result_attempts TO deermind_app;
        GRANT UPDATE(resolution,matched_event_ref,result_ref,resolved_at)
            ON runtime.waits TO deermind_app;
        GRANT UPDATE(state,handling_receipt_ref,failure_ref,updated_at)
            ON runtime.wait_handling TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration; preserve results and waits")
