"""建立领域根定义所需的身份、版本与请求收据。"""

from alembic import op

revision = "0012_domain_roots"
down_revision = "0011_ai_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """根身份与版本的循环外键在共同提交时检验。"""
    op.execute("""
        CREATE TABLE domain.object_identity (
            object_id uuid PRIMARY KEY,
            kind text NOT NULL CHECK (kind IN ('domain','task','solution','kc','task_instance')),
            domain_id uuid REFERENCES domain.object_identity(object_id),
            head_version bigint NOT NULL CHECK (head_version > 0),
            catalog_revision bigint CHECK (catalog_revision > 0),
            CHECK (
                (kind='domain' AND domain_id IS NULL AND catalog_revision IS NOT NULL)
                OR (kind<>'domain' AND domain_id IS NOT NULL AND catalog_revision IS NULL)
            )
        );
        CREATE INDEX ix_domain_identity_members
            ON domain.object_identity (domain_id,kind,object_id);

        CREATE TABLE domain.object_version (
            object_id uuid NOT NULL REFERENCES domain.object_identity(object_id),
            version bigint NOT NULL CHECK (version > 0),
            content_schema_version bigint NOT NULL CHECK (content_schema_version > 0),
            content jsonb NOT NULL CHECK (jsonb_typeof(content)='object'),
            is_deleted boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL,
            created_by jsonb NOT NULL CHECK (jsonb_typeof(created_by)='object'),
            change_note text NOT NULL CHECK (length(btrim(change_note)) > 0),
            source_event_id uuid NOT NULL,
            PRIMARY KEY (object_id,version)
        );
        CREATE INDEX ix_domain_version_source ON domain.object_version (source_event_id);
        ALTER TABLE domain.object_identity ADD CONSTRAINT fk_domain_identity_head
            FOREIGN KEY (object_id,head_version)
            REFERENCES domain.object_version (object_id,version) DEFERRABLE INITIALLY DEFERRED;

        CREATE TABLE domain.command_receipt (
            receipt_id uuid PRIMARY KEY,
            principal_id text NOT NULL,
            action text NOT NULL,
            scope_id text NOT NULL,
            request_id text NOT NULL,
            normalized_input jsonb NOT NULL CHECK (jsonb_typeof(normalized_input)='object'),
            input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
            state text NOT NULL CHECK (state IN ('accepted','completed','failed')),
            input_artifact_id uuid,
            runtime_ref uuid,
            result_ref jsonb,
            error jsonb,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (principal_id,action,scope_id,request_id)
        );

        GRANT SELECT, INSERT ON domain.object_identity, domain.object_version TO deermind_app;
        GRANT SELECT, INSERT ON domain.command_receipt TO deermind_app;
        GRANT UPDATE (state,result_ref,updated_at) ON domain.command_receipt TO deermind_app;
    """)


def downgrade() -> None:
    """领域版本关联不可逆事实，结构修正应追加迁移。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
