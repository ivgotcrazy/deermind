"""后台工作、执行尝试、授权和步骤收据；不创建业务工作或模型配置。"""

from alembic import op

revision = "0008_execution"
down_revision = "0007_event_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """身份和结果只追加，当前状态由底座在短事务内更新。"""
    op.execute("""
        CREATE TABLE runtime.executions (
            execution_id uuid PRIMARY KEY,
            kind text NOT NULL CHECK (kind IN ('ai_operation','handler')),
            owner text NOT NULL,
            entry_ref text NOT NULL,
            scope_kind text NOT NULL,
            implementation_ref jsonb NOT NULL,
            ai_config_ref uuid,
            scope_id uuid NOT NULL,
            acceptance_key text NOT NULL,
            input_ref jsonb NOT NULL,
            active_attempt_id uuid,
            state text NOT NULL CHECK (state IN
                ('ready','running','waiting','completed','failed','cancelled')),
            result_ref jsonb,
            failure_ref jsonb,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (owner,entry_ref,scope_id,acceptance_key),
            CHECK ((kind='ai_operation') = (ai_config_ref IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE TABLE runtime.execution_authorizations (
            execution_id uuid PRIMARY KEY REFERENCES runtime.executions(execution_id),
            initiator_ref jsonb NOT NULL,
            owner text NOT NULL,
            entry text NOT NULL,
            resource_scope jsonb NOT NULL,
            allowed_actions jsonb NOT NULL CHECK (jsonb_typeof(allowed_actions)='array'),
            basis_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE runtime.execution_attempts (
            attempt_id uuid PRIMARY KEY,
            execution_id uuid NOT NULL REFERENCES runtime.executions(execution_id),
            attempt_no bigint NOT NULL CHECK (attempt_no >= 1),
            retry_request_id text,
            previous_attempt_id uuid REFERENCES runtime.execution_attempts(attempt_id),
            workflow_id text NOT NULL UNIQUE,
            temporal_run_id text,
            accepted_at timestamptz NOT NULL,
            deadline_at timestamptz NOT NULL CHECK (deadline_at > accepted_at),
            state text NOT NULL CHECK (state IN
                ('ready','running','waiting','completed','failed','cancelled')),
            failure_ref jsonb,
            finished_at timestamptz,
            UNIQUE (execution_id,attempt_no),
            UNIQUE (execution_id,attempt_id)
        )
    """)
    # 组合外键防止当前指针误指向另一份工作的尝试；初次受理先插入再绑定。
    op.execute("""
        ALTER TABLE runtime.executions ADD CONSTRAINT fk_active_execution_attempt
        FOREIGN KEY (execution_id,active_attempt_id)
        REFERENCES runtime.execution_attempts(execution_id,attempt_id)
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_execution_retry
        ON runtime.execution_attempts(execution_id,retry_request_id)
        WHERE retry_request_id IS NOT NULL
    """)
    op.execute("""
        CREATE TABLE runtime.step_results (
            execution_id uuid NOT NULL REFERENCES runtime.executions(execution_id),
            step_name text NOT NULL,
            occurrence_key text NOT NULL,
            input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
            output_ref jsonb NOT NULL,
            owner_receipt_ref jsonb,
            completed_by_attempt uuid NOT NULL,
            created_at timestamptz NOT NULL,
            PRIMARY KEY (execution_id,step_name,occurrence_key),
            FOREIGN KEY (execution_id,completed_by_attempt)
                REFERENCES runtime.execution_attempts(execution_id,attempt_id)
        )
    """)
    op.execute("CREATE INDEX ix_executions_state ON runtime.executions(state,updated_at)")
    op.execute("""
        CREATE INDEX ix_execution_attempts_state
        ON runtime.execution_attempts(state,finished_at)
    """)
    for table in ("executions", "execution_authorizations", "execution_attempts", "step_results"):
        op.execute(f"GRANT SELECT, INSERT ON runtime.{table} TO deermind_app")
    op.execute("""
        GRANT UPDATE (active_attempt_id,state,result_ref,failure_ref,updated_at)
        ON runtime.executions TO deermind_app
    """)
    op.execute("""
        GRANT UPDATE (temporal_run_id,state,failure_ref,finished_at)
        ON runtime.execution_attempts TO deermind_app
    """)


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration; preserve execution and step history")
