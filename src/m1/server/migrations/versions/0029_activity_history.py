"""建立活动、消息和该空间的当前运行位置。"""

from alembic import op

revision = "0029_activity_history"
down_revision = "0028_goal_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """将历史投影与当前指针分别落表。"""
    op.execute("""
        CREATE TABLE interaction.inputs (
            input_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            request_id text NOT NULL,
            kind text NOT NULL CHECK (kind IN ('message','answer','activity_control','stop')),
            input jsonb NOT NULL,
            turn_epoch bigint NOT NULL CHECK (turn_epoch > 0),
            accepted_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE(scope_id, request_id)
        );
        CREATE TABLE interaction.messages (
            message_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            message_seq bigint NOT NULL CHECK (message_seq > 0),
            role text NOT NULL CHECK (role IN ('student','assistant','system')),
            parts jsonb NOT NULL,
            source_input_ref uuid REFERENCES interaction.inputs(input_id),
            source_trigger_ref uuid,
            committed_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE(scope_id, message_seq),
            CHECK (source_input_ref IS NOT NULL OR source_trigger_ref IS NOT NULL)
        );
        CREATE TABLE interaction.input_results (
            result_id uuid PRIMARY KEY,
            input_id uuid NOT NULL REFERENCES interaction.inputs(input_id),
            step_key text NOT NULL,
            outcome text NOT NULL CHECK (outcome IN (
                'completed','needs_input','blocked','failed','cancelled'
            )),
            message_refs jsonb NOT NULL DEFAULT '[]',
            activity_revision_refs jsonb NOT NULL DEFAULT '[]',
            error_ref jsonb,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (input_id, step_key)
        );
        CREATE TABLE interaction.activities (
            activity_id uuid PRIMARY KEY,
            scope_id uuid NOT NULL,
            root_id uuid NOT NULL,
            parent_id uuid,
            type text NOT NULL CHECK (type IN (
                'explanation','question_answer','detection','free_chat'
            )),
            name text NOT NULL,
            config_ref uuid NOT NULL REFERENCES interaction.resolved_configs(config_id),
            adoption_ref uuid NOT NULL,
            started_at timestamptz NOT NULL,
            first_message_ref uuid NOT NULL REFERENCES interaction.messages(message_id),
            source_event_id uuid NOT NULL,
            UNIQUE(scope_id, activity_id),
            FOREIGN KEY (scope_id, root_id)
                REFERENCES interaction.activities(scope_id, activity_id),
            FOREIGN KEY (scope_id, parent_id)
                REFERENCES interaction.activities(scope_id, activity_id),
            CHECK ((parent_id IS NULL) = (root_id = activity_id)),
            CHECK (parent_id IS DISTINCT FROM activity_id)
        );
        CREATE INDEX activities_root_order
            ON interaction.activities(scope_id, started_at DESC, activity_id DESC)
            WHERE parent_id IS NULL;
        CREATE INDEX activities_children
            ON interaction.activities(parent_id, started_at, activity_id);
        CREATE TABLE interaction.activity_revisions (
            activity_id uuid NOT NULL REFERENCES interaction.activities(activity_id),
            revision bigint NOT NULL CHECK (revision > 0),
            node_id text NOT NULL,
            run_state text NOT NULL CHECK (run_state IN (
                'active','waiting_child','paused','completed','cancelled','blocked'
            )),
            return_point jsonb,
            related_round_ref jsonb,
            reason text NOT NULL,
            source_input_ref uuid REFERENCES interaction.inputs(input_id),
            source_trigger_ref uuid,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY (activity_id, revision),
            CHECK (source_input_ref IS NOT NULL OR source_trigger_ref IS NOT NULL)
        );
        CREATE TABLE interaction.activity_heads (
            activity_id uuid PRIMARY KEY,
            revision bigint NOT NULL,
            FOREIGN KEY (activity_id, revision)
                REFERENCES interaction.activity_revisions(activity_id, revision)
        );
        CREATE TABLE interaction.message_assignments (
            message_id uuid PRIMARY KEY REFERENCES interaction.messages(message_id),
            activity_id uuid NOT NULL REFERENCES interaction.activities(activity_id),
            assigned_by_input_ref uuid REFERENCES interaction.inputs(input_id),
            source_trigger_ref uuid,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            CHECK (assigned_by_input_ref IS NOT NULL OR source_trigger_ref IS NOT NULL)
        );
        CREATE INDEX message_assignment_activity
            ON interaction.message_assignments(activity_id, message_id);
        CREATE TABLE interaction.space_runtime (
            scope_id uuid PRIMARY KEY,
            current_leaf_ref uuid,
            active_input_id uuid REFERENCES interaction.inputs(input_id),
            turn_epoch bigint NOT NULL DEFAULT 0,
            last_message_seq bigint NOT NULL DEFAULT 0,
            FOREIGN KEY (scope_id, current_leaf_ref)
                REFERENCES interaction.activities(scope_id, activity_id)
        );
        GRANT SELECT, INSERT ON interaction.activity_heads, interaction.space_runtime
            TO deermind_app;
        GRANT UPDATE (revision) ON interaction.activity_heads TO deermind_app;
        GRANT UPDATE(current_leaf_ref, active_input_id, turn_epoch, last_message_seq)
            ON interaction.space_runtime TO deermind_app;
    """)
    for table in (
        "inputs",
        "input_results",
        "messages",
        "activities",
        "activity_revisions",
        "message_assignments",
    ):
        op.execute(f"""
            CREATE INDEX interaction_{table}_event ON interaction.{table}(source_event_id);
            GRANT SELECT, INSERT ON interaction.{table} TO deermind_app;
        """)


def downgrade() -> None:
    """保留已产生的交互历史。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
