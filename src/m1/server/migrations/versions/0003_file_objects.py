"""登记不可变文件；上传会话和HTTP上传在教材上传增量实现。"""

from alembic import op

revision = "0003_file_objects"
down_revision = "0002_atomic_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """文件登记只追加；原件、派生物和事实附件共同使用文件隔离层。"""
    op.execute("""
        CREATE TABLE runtime.file_objects (
            file_id uuid PRIMARY KEY,
            backend text NOT NULL CHECK (backend IN ('local', 'pvc', 'object')),
            storage_key text NOT NULL CHECK (storage_key <> ''),
            media_type text NOT NULL CHECK (media_type <> ''),
            byte_size bigint NOT NULL CHECK (byte_size >= 0),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            category text NOT NULL CHECK (category IN
                ('original', 'page', 'render', 'ai_material', 'ai_candidate',
                 'sdk_payload', 'fact')),
            artifact_key text,
            source_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(source_refs) = 'array'),
            transform_ref jsonb CHECK
                (transform_ref IS NULL OR jsonb_typeof(transform_ref) = 'object'),
            created_at timestamptz NOT NULL,
            UNIQUE (backend, storage_key),
            CHECK (artifact_key IS NULL OR artifact_key <> '')
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_file_objects_artifact ON runtime.file_objects (artifact_key)
        WHERE artifact_key IS NOT NULL
    """)
    op.execute("GRANT SELECT, INSERT ON runtime.file_objects TO deermind_app")


def downgrade() -> None:
    raise RuntimeError("File registrations cannot be discarded by an automatic downgrade")
