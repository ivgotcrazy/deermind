"""增加凭据与可撤销登录会话；不创建账号，不写入默认密码。"""

from alembic import op

revision = "0005_auth_sessions"
down_revision = "0004_projection_rebuilds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """认证控制数据不从事件重建；仅开放登录读取及会话撤销权限。"""
    op.execute("""
        CREATE TABLE product.credentials (
            account_id uuid PRIMARY KEY REFERENCES product.accounts(account_id),
            password_hash text NOT NULL,
            credential_revision bigint NOT NULL CHECK (credential_revision >= 1),
            changed_at timestamptz NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE product.auth_sessions (
            session_id uuid PRIMARY KEY,
            account_id uuid NOT NULL REFERENCES product.accounts(account_id),
            token_hash text NOT NULL UNIQUE,
            credential_revision bigint NOT NULL CHECK (credential_revision >= 1),
            csrf_token text NOT NULL,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz,
            CHECK (expires_at > created_at)
        )
    """)
    op.execute("""
        CREATE INDEX ix_auth_sessions_account
        ON product.auth_sessions(account_id,revoked_at)
    """)
    op.execute("CREATE INDEX ix_auth_sessions_expires ON product.auth_sessions(expires_at)")
    op.execute("GRANT SELECT ON product.credentials TO deermind_app")
    op.execute("GRANT SELECT, INSERT ON product.auth_sessions TO deermind_app")
    op.execute("GRANT UPDATE (revoked_at) ON product.auth_sessions TO deermind_app")
    # 只保存限流所需摘要，不保存原始账号、IP、密码或Cookie。
    op.execute("""
        CREATE TABLE product.login_attempts (
            attempt_id uuid PRIMARY KEY,
            login_digest text NOT NULL CHECK (login_digest ~ '^[0-9a-f]{64}$'),
            source_digest text NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
            admitted_at timestamptz NOT NULL,
            outcome text NOT NULL CHECK
                (outcome IN ('pending','success','invalid','unavailable'))
        )
    """)
    op.execute(
        "CREATE INDEX ix_login_attempts_name ON product.login_attempts(login_digest,admitted_at)"
    )
    op.execute(
        "CREATE INDEX ix_login_attempts_source ON product.login_attempts(source_digest,admitted_at)"
    )
    op.execute("GRANT SELECT, INSERT ON product.login_attempts TO deermind_app")
    op.execute("GRANT UPDATE (outcome) ON product.login_attempts TO deermind_app")


def downgrade() -> None:
    raise RuntimeError("Use a reviewed forward migration; do not discard authentication records")
