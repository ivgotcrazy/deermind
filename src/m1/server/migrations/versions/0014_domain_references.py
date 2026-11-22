"""为领域精确版本关系建立只追加查询索引。"""

from alembic import op

revision = "0014_domain_references"
down_revision = "0013_kc_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE domain.object_reference (
            owner_id uuid NOT NULL,
            owner_version bigint NOT NULL,
            path text NOT NULL CHECK (left(path,1)='/'),
            relation_kind text NOT NULL CHECK (relation_kind IN (
                'task_method','task_prerequisite','prerequisite_method_scope',
                'solution_kc','instance_task','reference_solution'
            )),
            target_id uuid NOT NULL,
            target_version bigint NOT NULL,
            PRIMARY KEY (owner_id,owner_version,path),
            FOREIGN KEY (owner_id,owner_version)
                REFERENCES domain.object_version (object_id,version),
            FOREIGN KEY (target_id,target_version)
                REFERENCES domain.object_version (object_id,version)
        );
        CREATE INDEX ix_domain_reference_target
            ON domain.object_reference (target_id,target_version,relation_kind);
        CREATE INDEX ix_domain_reference_owner
            ON domain.object_reference (owner_id,owner_version,relation_kind);
        GRANT SELECT, INSERT ON domain.object_reference TO deermind_app;
    """)


def downgrade() -> None:
    """已提交事实的索引通过审核的前向迁移修正。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
