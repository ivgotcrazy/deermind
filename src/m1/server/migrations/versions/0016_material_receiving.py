"""建立教材登记、原件和上传记录。"""

from alembic import op

revision = "0016_material_receiving"
down_revision = "0015_kc_test_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE runtime.file_uploads (
            upload_id uuid PRIMARY KEY,
            principal_id text NOT NULL,
            purpose text NOT NULL CHECK (purpose='material_source'),
            resource_ref jsonb,
            domain_ref jsonb NOT NULL,
            request_id text NOT NULL,
            original_name text NOT NULL,
            declared_media_type text NOT NULL,
            declared_size bigint NOT NULL CHECK (declared_size>0),
            state text NOT NULL CHECK (state IN ('receiving','ready','failed')),
            write_attempt_id uuid NOT NULL,
            lease_until timestamptz NOT NULL,
            file_id uuid UNIQUE REFERENCES runtime.file_objects(file_id),
            page_count integer CHECK (page_count BETWEEN 1 AND 600),
            error jsonb,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (principal_id,purpose,request_id),
            CHECK ((state='ready')=(file_id IS NOT NULL)),
            CHECK ((state='ready')=(page_count IS NOT NULL)),
            CHECK ((state='failed')=(error IS NOT NULL))
        );
        CREATE TABLE product.material_import (
            import_id uuid PRIMARY KEY,
            textbook_id uuid NOT NULL UNIQUE,
            status text NOT NULL CHECK (status IN ('active','deleted')),
            revision bigint NOT NULL CHECK (revision>0),
            source_revision bigint NOT NULL DEFAULT 0 CHECK (source_revision>=0),
            content_revision bigint NOT NULL DEFAULT 0 CHECK (content_revision>=0),
            active_request_ref uuid,
            next_message_seq bigint NOT NULL DEFAULT 1 CHECK (next_message_seq>0),
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE product.textbook (
            textbook_id uuid PRIMARY KEY,
            domain_id uuid NOT NULL,
            import_id uuid NOT NULL UNIQUE REFERENCES product.material_import(import_id),
            metadata jsonb NOT NULL CHECK (jsonb_typeof(metadata)='object'),
            metadata_revision bigint NOT NULL CHECK (metadata_revision>0),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        ALTER TABLE product.material_import ADD FOREIGN KEY (textbook_id)
            REFERENCES product.textbook(textbook_id) DEFERRABLE INITIALLY DEFERRED;
        CREATE TABLE product.material_source (
            source_id uuid PRIMARY KEY,
            import_id uuid NOT NULL REFERENCES product.material_import(import_id),
            file_id uuid NOT NULL,
            original_name text NOT NULL,
            source_order bigint NOT NULL CHECK (source_order>0),
            pages jsonb NOT NULL CHECK (jsonb_typeof(pages)='array'),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (import_id,file_id),
            UNIQUE (import_id,source_order)
        );
        CREATE INDEX ix_textbook_domain ON product.textbook(domain_id,textbook_id);
        CREATE INDEX ix_textbook_event ON product.textbook(source_event_id);
        CREATE INDEX ix_material_import_event ON product.material_import(source_event_id);
        CREATE INDEX ix_material_source_event ON product.material_source(source_event_id);
        GRANT SELECT, INSERT, UPDATE ON runtime.file_uploads TO deermind_app;
        GRANT SELECT, INSERT ON product.material_import, product.textbook,
            product.material_source TO deermind_app;
        GRANT UPDATE (revision,source_revision,updated_at,source_event_id)
            ON product.material_import TO deermind_app;
    """)


def downgrade() -> None:
    """教材原始事实通过前向迁移保持。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
