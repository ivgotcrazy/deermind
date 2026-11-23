"""保存不可变 Claim 修订和派生头索引。"""

from alembic import op

revision = "0024_claim_definitions"
down_revision = "0023_material_deletion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE evaluation.claim (
            claim_id uuid PRIMARY KEY,
            domain_id uuid NOT NULL,
            task_id uuid NOT NULL,
            task_version bigint NOT NULL CHECK (task_version>0),
            head_revision bigint NOT NULL CHECK (head_revision>0),
            created_at timestamptz NOT NULL,
            UNIQUE (task_id,task_version)
        );
        CREATE TABLE evaluation.claim_version (
            claim_id uuid NOT NULL REFERENCES evaluation.claim(claim_id),
            revision bigint NOT NULL CHECK (revision>0),
            definition jsonb NOT NULL CHECK (jsonb_typeof(definition)='object'),
            gaps jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(gaps)='array'),
            request_ref text NOT NULL,
            actor_ref jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY (claim_id,revision)
        );
        ALTER TABLE evaluation.claim ADD FOREIGN KEY (claim_id,head_revision)
            REFERENCES evaluation.claim_version(claim_id,revision) DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_claim_domain_task ON evaluation.claim(domain_id,task_id,task_version);
        CREATE INDEX ix_claim_version_event ON evaluation.claim_version(source_event_id);
        GRANT SELECT,INSERT ON evaluation.claim,evaluation.claim_version TO deermind_app;
        GRANT UPDATE (head_revision) ON evaluation.claim TO deermind_app;
    """)


def downgrade() -> None:
    """历史评价定义只能通过前向迁移维护。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
