"""AI配置、调用、工具及候选投影；用量独立汇总，原始事实不可覆盖。"""

from alembic import op

revision = "0011_ai_calls"
down_revision = "0010_waits_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """逐表建立约束；应用没有删除权限，结构调整只能追加迁移。"""
    op.execute("""
        CREATE TABLE ai.execution_configs (
            execution_id uuid PRIMARY KEY REFERENCES runtime.executions(execution_id),
            config_revision text NOT NULL CHECK (length(config_revision)>0),
            config_hash text NOT NULL CHECK (config_hash ~ '^[0-9a-f]{64}$'),
            config jsonb NOT NULL CHECK (jsonb_typeof(config)='object'),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL REFERENCES runtime.events(event_id)
        );
        CREATE TABLE ai.ai_calls (
            call_id uuid PRIMARY KEY,
            execution_id uuid NOT NULL REFERENCES ai.execution_configs(execution_id),
            step_key text NOT NULL CHECK (length(step_key)>0),
            call_key text NOT NULL CHECK (length(call_key)>0),
            input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
            purpose text NOT NULL CHECK (length(purpose)>0),
            schema_ref jsonb NOT NULL,
            input_ref jsonb NOT NULL,
            state text NOT NULL CHECK (state IN
                ('pending','running','completed','failed','cancelled')),
            candidate_ref uuid,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            UNIQUE (execution_id,step_key,call_key),
            CHECK ((state='completed') = (candidate_ref IS NOT NULL))
        );
        CREATE TABLE ai.ai_call_attempts (
            call_id uuid NOT NULL REFERENCES ai.ai_calls(call_id),
            attempt_id uuid NOT NULL,
            execution_attempt_id uuid NOT NULL REFERENCES runtime.execution_attempts(attempt_id),
            attempt_no bigint NOT NULL CHECK (attempt_no>0),
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            outcome text NOT NULL CHECK (outcome IN
                ('running','completed','failed','cancelled','unknown')),
            error jsonb,
            valid_candidate boolean NOT NULL DEFAULT false,
            source_event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            PRIMARY KEY (call_id,attempt_id),
            UNIQUE (call_id,attempt_no),
            CHECK ((outcome='running') = (finished_at IS NULL)),
            CHECK (NOT valid_candidate OR outcome='completed')
        );
        CREATE TABLE ai.execution_usage (
            execution_id uuid PRIMARY KEY REFERENCES ai.execution_configs(execution_id),
            request_count bigint NOT NULL DEFAULT 0 CHECK (request_count>=0),
            tool_count bigint NOT NULL DEFAULT 0 CHECK (tool_count>=0),
            repair_count bigint NOT NULL DEFAULT 0 CHECK (repair_count>=0),
            known_input_tokens bigint NOT NULL DEFAULT 0 CHECK (known_input_tokens>=0),
            known_output_tokens bigint NOT NULL DEFAULT 0 CHECK (known_output_tokens>=0),
            reserved_input_tokens bigint NOT NULL DEFAULT 0 CHECK (reserved_input_tokens>=0),
            reserved_output_tokens bigint NOT NULL DEFAULT 0 CHECK (reserved_output_tokens>=0),
            unknown_request_count bigint NOT NULL DEFAULT 0 CHECK (unknown_request_count>=0),
            updated_at timestamptz NOT NULL
        );
        CREATE TABLE ai.model_requests (
            call_id uuid NOT NULL REFERENCES ai.ai_calls(call_id),
            attempt_id uuid NOT NULL,
            request_ordinal bigint NOT NULL CHECK (request_ordinal>0),
            transport_attempt bigint NOT NULL CHECK (transport_attempt>0),
            model text NOT NULL CHECK (length(model)>0),
            request_ref jsonb NOT NULL,
            reserved_input_tokens bigint NOT NULL CHECK (reserved_input_tokens>=0),
            reserved_output_tokens bigint NOT NULL CHECK (reserved_output_tokens>=0),
            actual_input_tokens bigint CHECK (actual_input_tokens>=0),
            actual_output_tokens bigint CHECK (actual_output_tokens>=0),
            usage_state text NOT NULL CHECK (usage_state IN ('reserved','known','unknown')),
            provider_request_id text,
            outcome text NOT NULL CHECK (outcome IN ('pending','success','failed','unknown')),
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            response_ref jsonb,
            source_event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            PRIMARY KEY (call_id,attempt_id,request_ordinal,transport_attempt),
            FOREIGN KEY (call_id,attempt_id) REFERENCES ai.ai_call_attempts(call_id,attempt_id),
            CHECK ((usage_state='known' AND actual_input_tokens IS NOT NULL
                    AND actual_output_tokens IS NOT NULL)
                OR (usage_state<>'known' AND actual_input_tokens IS NULL
                    AND actual_output_tokens IS NULL)),
            CHECK ((outcome='pending') = (finished_at IS NULL))
        );
        CREATE TABLE ai.tool_actions (
            tool_action_key text NOT NULL CHECK (length(tool_action_key)>0),
            attempt_id uuid NOT NULL,
            call_id uuid NOT NULL REFERENCES ai.ai_calls(call_id),
            tool_name text NOT NULL,
            parameters_ref jsonb NOT NULL,
            result_ref jsonb,
            authorization_result text NOT NULL CHECK (authorization_result IN ('allowed','denied')),
            work_key text,
            owner_receipt_ref jsonb,
            outcome text NOT NULL CHECK (outcome IN ('pending','completed','failed','denied')),
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            source_event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            PRIMARY KEY (tool_action_key,attempt_id),
            FOREIGN KEY (call_id,attempt_id) REFERENCES ai.ai_call_attempts(call_id,attempt_id),
            CHECK ((outcome='pending') = (finished_at IS NULL)),
            CHECK ((outcome='denied') = (authorization_result='denied'))
        );
        CREATE TABLE ai.ai_candidates (
            candidate_id uuid PRIMARY KEY,
            call_id uuid NOT NULL UNIQUE REFERENCES ai.ai_calls(call_id),
            schema_ref jsonb NOT NULL,
            content jsonb NOT NULL CHECK (jsonb_typeof(content)='object'),
            material_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(material_refs)='array'),
            tool_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(tool_refs)='array'),
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            UNIQUE (call_id,candidate_id)
        );
        ALTER TABLE ai.ai_calls ADD FOREIGN KEY (call_id,candidate_ref)
            REFERENCES ai.ai_candidates(call_id,candidate_id);
    """)

    # 权限按表角色授予。不可变配置和候选不授予UPDATE；无表授予DELETE。
    immutable = ("execution_configs", "ai_candidates")
    mutable = ("ai_calls", "ai_call_attempts", "model_requests", "tool_actions")
    for name in (*immutable, *mutable):
        op.execute(f"CREATE INDEX ix_{name}_source_event ON ai.{name}(source_event_id)")
        op.execute(f"REVOKE ALL ON ai.{name} FROM PUBLIC, deermind_app")
        permission = "SELECT, INSERT" if name in immutable else "SELECT, INSERT, UPDATE"
        op.execute(f"GRANT {permission} ON ai.{name} TO deermind_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ai.execution_usage TO deermind_app")


def downgrade() -> None:
    """不删除调用历史；需回退时另交经审阅的向前迁移。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
