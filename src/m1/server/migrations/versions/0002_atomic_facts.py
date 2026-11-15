"""建立首批事实、序号、投影及收据表；历史DDL不导入可变业务模型。"""

from alembic import op

revision = "0002_atomic_facts"
down_revision = "0001_infrastructure_schemas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """按数据库分册建表；应用账号无事件和投影收据的修改、删除权限。"""
    op.execute("""
        CREATE TABLE runtime.events (
            event_id uuid PRIMARY KEY,
            commit_id uuid NOT NULL,
            event_type text NOT NULL,
            schema_version bigint NOT NULL CHECK (schema_version > 0),
            producer text NOT NULL,
            scope_kind text NOT NULL,
            scope_id uuid NOT NULL,
            owner_ref jsonb NOT NULL,
            subject_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            actor_ref jsonb,
            source_execution_ref uuid,
            source_request_id text,
            causation_event_id uuid REFERENCES runtime.events(event_id),
            correlation_id uuid NOT NULL,
            scope_event_seq bigint NOT NULL CHECK (scope_event_seq > 0),
            occurred_at timestamptz,
            recorded_at timestamptz NOT NULL,
            time_basis text NOT NULL
                CHECK (time_basis IN ('server_recorded', 'referenced_fact', 'unknown')),
            time_source_ref jsonb,
            client_reported_at timestamptz,
            payload jsonb NOT NULL,
            CONSTRAINT uq_events_scope_seq UNIQUE (scope_kind, scope_id, scope_event_seq),
            CHECK (NULLIF(source_request_id, '') IS NOT NULL OR causation_event_id IS NOT NULL),
            CHECK (jsonb_typeof(subject_refs) = 'array'),
            CHECK (jsonb_typeof(payload) = 'object' AND payload ? 'records'
                   AND jsonb_typeof(payload->'records') = 'array'),
            CHECK ((time_basis = 'unknown' AND occurred_at IS NULL AND time_source_ref IS NULL)
                OR (time_basis = 'server_recorded'
                    AND occurred_at IS NOT NULL AND time_source_ref IS NULL)
                OR (time_basis = 'referenced_fact'
                    AND occurred_at IS NOT NULL AND time_source_ref IS NOT NULL))
        )
    """)
    for name, columns in (
        ("commit", "commit_id"),
        ("scope_type_seq", "scope_kind, scope_id, event_type, scope_event_seq"),
        ("scope_recorded", "scope_kind, scope_id, recorded_at, event_id"),
        ("type_recorded", "event_type, recorded_at"),
        ("execution", "source_execution_ref"),
        ("correlation", "correlation_id"),
        ("cause", "causation_event_id"),
    ):
        op.execute(f"CREATE INDEX ix_events_{name} ON runtime.events ({columns})")

    op.execute("""
        CREATE TABLE runtime.scope_event_heads (
            scope_kind text NOT NULL,
            scope_id uuid NOT NULL,
            last_seq bigint NOT NULL DEFAULT 0 CHECK (last_seq >= 0),
            PRIMARY KEY (scope_kind, scope_id)
        )
    """)
    op.execute("""
        CREATE TABLE runtime.projection_receipts (
            projector_id text NOT NULL,
            generation bigint NOT NULL CHECK (generation >= 1),
            event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            applied_at timestamptz NOT NULL,
            PRIMARY KEY (projector_id, generation, event_id)
        )
    """)
    op.execute("CREATE INDEX ix_projection_receipts_event ON runtime.projection_receipts(event_id)")

    op.execute("""
        CREATE TABLE product.accounts (
            account_id uuid PRIMARY KEY,
            login_identifier text NOT NULL UNIQUE CHECK (length(login_identifier) > 0),
            display_name text NOT NULL CHECK (length(display_name) > 0),
            role text NOT NULL CHECK (role IN ('student', 'admin')),
            status text NOT NULL CHECK (status IN ('active', 'disabled')),
            revision bigint NOT NULL CHECK (revision >= 1),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        )
    """)
    op.execute("CREATE INDEX ix_accounts_source ON product.accounts(source_event_id)")
    op.execute("""
        CREATE TABLE product.command_receipt (
            request_ref uuid PRIMARY KEY,
            principal_id text NOT NULL,
            action text NOT NULL,
            scope_id text NOT NULL,
            request_id text NOT NULL,
            input_digest text NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$'),
            normalized_input jsonb NOT NULL,
            state text NOT NULL CHECK (state IN ('accepted', 'completed', 'failed')),
            result_ref jsonb,
            error jsonb,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT uq_command_receipt_request
                UNIQUE (principal_id, action, scope_id, request_id)
        )
    """)

    # 只开放本增量用到的写入；未来可变账号投影在其增量中扩展权限。
    for table in ("runtime.events", "runtime.projection_receipts", "product.accounts"):
        op.execute(f"GRANT SELECT, INSERT ON {table} TO deermind_app")
    op.execute("GRANT SELECT, INSERT ON runtime.scope_event_heads TO deermind_app")
    op.execute("GRANT UPDATE (last_seq) ON runtime.scope_event_heads TO deermind_app")
    op.execute("GRANT SELECT, INSERT ON product.command_receipt TO deermind_app")
    op.execute(
        "GRANT UPDATE (state, result_ref, error, updated_at) "
        "ON product.command_receipt TO deermind_app"
    )


def downgrade() -> None:
    """事实不可通过回滚迁移丢弃；修订应另写向前迁移。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
