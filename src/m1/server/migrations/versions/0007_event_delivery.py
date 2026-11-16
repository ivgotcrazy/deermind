"""事件发布安排和订阅收据；不创建业务订阅或Temporal执行任务。"""

from alembic import op

revision = "0007_event_delivery"
down_revision = "0006_account_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """交接控制数据与业务事实同库提交，应用不能删除收据及历史尝试。"""
    op.execute("""
        CREATE TABLE runtime.handoffs (
            handoff_id uuid PRIMARY KEY,
            kind text NOT NULL CHECK (kind IN ('publish','start','signal','cancel')),
            logical_key text NOT NULL,
            source_ref jsonb NOT NULL,
            payload jsonb NOT NULL,
            state text NOT NULL CHECK (state IN ('pending','leased','delivered','exhausted')),
            next_attempt_at timestamptz NOT NULL,
            lease_owner text,
            lease_until timestamptz,
            subscription_snapshot jsonb,
            delivery_id uuid,
            stream_name text,
            stream_sequence bigint CHECK (stream_sequence > 0),
            authorization_ref jsonb,
            last_failure_ref jsonb,
            created_at timestamptz NOT NULL,
            UNIQUE (kind,logical_key),
            CHECK ((state = 'leased') = (lease_owner IS NOT NULL AND lease_until IS NOT NULL)),
            CHECK ((kind = 'publish') =
                   (subscription_snapshot IS NOT NULL AND delivery_id IS NOT NULL)),
            CHECK ((stream_name IS NULL) = (stream_sequence IS NULL))
        )
    """)
    op.execute("""
        CREATE TABLE runtime.handoff_attempts (
            handoff_id uuid NOT NULL REFERENCES runtime.handoffs(handoff_id),
            attempt_no bigint NOT NULL CHECK (attempt_no >= 1),
            started_at timestamptz NOT NULL,
            finished_at timestamptz,
            outcome text NOT NULL CHECK (outcome IN ('delivered','failed','unknown')),
            error jsonb,
            transport_receipt jsonb,
            PRIMARY KEY (handoff_id,attempt_no)
        )
    """)
    op.execute("""
        CREATE TABLE runtime.subscription_receipts (
            subscriber_id text NOT NULL,
            event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            handler_revision text NOT NULL,
            disposition text NOT NULL CHECK (disposition IN ('accepted','rejected','ignored')),
            arrangement_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            error jsonb,
            created_at timestamptz NOT NULL,
            PRIMARY KEY (subscriber_id,event_id),
            CHECK (jsonb_typeof(arrangement_refs) = 'array'),
            CHECK ((disposition = 'rejected') = (error IS NOT NULL))
        )
    """)
    op.execute("""
        CREATE TABLE runtime.delivery_failures (
            failure_id uuid PRIMARY KEY,
            handoff_id uuid NOT NULL REFERENCES runtime.handoffs(handoff_id),
            event_id uuid NOT NULL REFERENCES runtime.events(event_id),
            subscriber_id text NOT NULL,
            failure_kind text NOT NULL CHECK (failure_kind IN
                ('delivery_exhausted','consumer_missing','transport_lost','rejected','unknown')),
            state text NOT NULL CHECK (state IN ('needs_check','confirmed','resolved')),
            basis_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            recovery_ref jsonb,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (handoff_id,subscriber_id,failure_kind)
        )
    """)
    op.execute("CREATE INDEX ix_handoffs_due ON runtime.handoffs(state,next_attempt_at)")
    op.execute("CREATE INDEX ix_handoffs_source ON runtime.handoffs(kind,source_ref)")
    op.execute("""
        CREATE UNIQUE INDEX uq_handoffs_delivery ON runtime.handoffs(delivery_id)
        WHERE kind='publish'
    """)
    op.execute("""
        CREATE INDEX ix_delivery_failure_event
        ON runtime.delivery_failures(event_id,subscriber_id)
    """)
    op.execute("""
        CREATE INDEX ix_delivery_failure_state
        ON runtime.delivery_failures(state,updated_at)
    """)
    for name in ("handoffs", "handoff_attempts", "subscription_receipts", "delivery_failures"):
        op.execute(f"GRANT SELECT, INSERT ON runtime.{name} TO deermind_app")
    op.execute("""
        GRANT UPDATE (state,next_attempt_at,lease_owner,lease_until,stream_name,
                      stream_sequence,last_failure_ref)
        ON runtime.handoffs TO deermind_app
    """)
    op.execute("""
        GRANT UPDATE (finished_at,outcome,error,transport_receipt)
        ON runtime.handoff_attempts TO deermind_app
    """)
    op.execute("""
        GRANT UPDATE (state,basis_refs,recovery_ref,updated_at)
        ON runtime.delivery_failures TO deermind_app
    """)


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration; do not discard delivery receipts")
