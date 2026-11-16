"""接线监护关系和首次确认；只迁移结构，不推定任何学生已经同意。"""

from alembic import op

revision = "0006_account_usage"
down_revision = "0005_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """事实投影保存关系和确认，凭据仍是独立的受保护控制数据。"""
    op.execute("""
        CREATE TABLE product.guardian_records (
            guardian_id uuid PRIMARY KEY,
            verified_identity_ref jsonb NOT NULL UNIQUE,
            display_name text NOT NULL CHECK (length(display_name) > 0),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE product.student_guardian_relations (
            relation_id uuid PRIMARY KEY,
            student_id uuid NOT NULL REFERENCES product.accounts(account_id),
            guardian_id uuid NOT NULL REFERENCES product.guardian_records(guardian_id),
            revision bigint NOT NULL CHECK (revision >= 1),
            verification_ref jsonb NOT NULL,
            relation_state text NOT NULL CHECK (relation_state IN ('active','ended')),
            previous_relation_id uuid REFERENCES product.student_guardian_relations(relation_id),
            actor_ref jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (student_id, guardian_id, revision)
        )
    """)
    op.execute("""
        CREATE TABLE product.usage_confirmations (
            confirmation_id uuid PRIMARY KEY,
            student_id uuid NOT NULL REFERENCES product.accounts(account_id),
            kind text NOT NULL CHECK (kind IN ('guardian_consent','student_assent')),
            notice_ref jsonb NOT NULL,
            decision text NOT NULL CHECK (decision IN ('accepted','declined','pending')),
            source_ref jsonb NOT NULL,
            actor_ref jsonb NOT NULL,
            occurred_at timestamptz,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE product.usage_conditions (
            student_id uuid PRIMARY KEY REFERENCES product.accounts(account_id),
            revision bigint NOT NULL CHECK (revision >= 1),
            confirmation_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            eligibility text NOT NULL CHECK (eligibility IN ('allowed','blocked','pending')),
            reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
            updated_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        )
    """)
    for name in (
        "guardian_records",
        "student_guardian_relations",
        "usage_confirmations",
        "usage_conditions",
    ):
        op.execute(f"CREATE INDEX ix_{name}_source ON product.{name}(source_event_id)")
        op.execute(f"GRANT SELECT, INSERT ON product.{name} TO deermind_app")
    op.execute("""
        CREATE INDEX ix_usage_confirmations_student
        ON product.usage_confirmations(student_id,kind,created_at)
    """)
    op.execute("""
        GRANT UPDATE (login_identifier,display_name,status,revision,source_event_id)
        ON product.accounts TO deermind_app
    """)
    op.execute("""
        GRANT UPDATE (revision,confirmation_refs,eligibility,reasons,updated_at,source_event_id)
        ON product.usage_conditions TO deermind_app
    """)
    op.execute("GRANT INSERT ON product.credentials TO deermind_app")
    op.execute("""
        GRANT UPDATE (password_hash,credential_revision,changed_at)
        ON product.credentials TO deermind_app
    """)


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration; do not discard account confirmations")
