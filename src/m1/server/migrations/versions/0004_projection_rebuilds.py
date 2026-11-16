"""增加投影扫描位置和获准的重建维护记录，不修改历史事实。"""

from alembic import op

revision = "0004_projection_rebuilds"
down_revision = "0003_file_objects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """维护记录及副本仅由迁移账号操作；应用暂不取得扫描写权限。"""
    op.execute("""
        CREATE TABLE runtime.projection_offsets (
            projector_id text NOT NULL,
            generation bigint NOT NULL CHECK (generation >= 1),
            scope_kind text NOT NULL,
            scope_id uuid NOT NULL,
            scanned_through_seq bigint NOT NULL DEFAULT 0,
            history_upper_seq bigint NOT NULL CHECK (history_upper_seq >= 0),
            state text NOT NULL CHECK (state IN ('catching_up','live','blocked','completed')),
            error jsonb,
            updated_at timestamptz NOT NULL,
            PRIMARY KEY (projector_id,generation,scope_kind,scope_id),
            CHECK (scanned_through_seq BETWEEN 0 AND history_upper_seq),
            CHECK ((state='blocked') = (error IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE INDEX ix_projection_offsets_state
        ON runtime.projection_offsets(projector_id,generation,state)
    """)
    op.execute("""
        CREATE TABLE runtime.projection_rebuilds (
            rebuild_id uuid PRIMARY KEY,
            projector_id text NOT NULL,
            generation bigint NOT NULL CHECK (generation > 1),
            implementation_digest text NOT NULL CHECK
                (implementation_digest ~ '^[0-9a-f]{64}$'),
            scope_bounds jsonb NOT NULL CHECK
                (jsonb_typeof(scope_bounds)='array' AND jsonb_array_length(scope_bounds)>0),
            stage_relation text NOT NULL UNIQUE,
            operator_id text NOT NULL CHECK (operator_id <> ''),
            authorization_ref text NOT NULL CHECK (authorization_ref <> ''),
            state text NOT NULL CHECK (state IN ('building','completed','failed')),
            result_event_id uuid REFERENCES runtime.events(event_id),
            error jsonb,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (projector_id,generation),
            CHECK ((state='building') = (result_event_id IS NULL)),
            CHECK ((state='failed') = (error IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE INDEX ix_projection_rebuilds_state
        ON runtime.projection_rebuilds(state,created_at)
    """)


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration; do not discard rebuild records")
