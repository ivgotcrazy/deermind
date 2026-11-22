"""建立检验路径确认和固定依据的只追加投影。"""

from alembic import op

revision = "0015_kc_test_paths"
down_revision = "0014_domain_references"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE domain.artifact (
            artifact_id uuid PRIMARY KEY,
            domain_id uuid NOT NULL REFERENCES domain.object_identity(object_id),
            kind text NOT NULL CHECK (kind IN (
                'input','definition_candidate','classification_check','use_check','readiness_check'
            )),
            input_ref jsonb,
            definition_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(definition_refs)='array'),
            payload jsonb NOT NULL CHECK (jsonb_typeof(payload)='object'),
            rule_ref jsonb,
            model_call_ref jsonb,
            command_ref jsonb,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE INDEX ix_domain_artifact_source ON domain.artifact(source_event_id);
        CREATE INDEX ix_domain_artifact_kind ON domain.artifact(domain_id,kind,artifact_id);

        CREATE TABLE domain.kc_test_path (
            confirmation_id uuid PRIMARY KEY,
            kc_id uuid NOT NULL,
            kc_version bigint NOT NULL,
            task_id uuid NOT NULL,
            task_version bigint NOT NULL,
            solution_id uuid NOT NULL,
            solution_version bigint NOT NULL,
            basis_artifact_id uuid NOT NULL REFERENCES domain.artifact(artifact_id),
            confirmed_by jsonb NOT NULL CHECK (jsonb_typeof(confirmed_by)='object'),
            confirmed_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (task_id,task_version,solution_id,solution_version,kc_id,kc_version),
            FOREIGN KEY (kc_id,kc_version) REFERENCES domain.object_version(object_id,version),
            FOREIGN KEY (task_id,task_version) REFERENCES domain.object_version(object_id,version),
            FOREIGN KEY (solution_id,solution_version)
                REFERENCES domain.object_version(object_id,version)
        );
        CREATE INDEX ix_domain_kc_path_source ON domain.kc_test_path(source_event_id);
        GRANT SELECT, INSERT ON domain.artifact, domain.kc_test_path TO deermind_app;
        GRANT UPDATE (error,input_artifact_id) ON domain.command_receipt TO deermind_app;
        ALTER TABLE domain.command_receipt ADD CONSTRAINT fk_domain_receipt_input
            FOREIGN KEY (input_artifact_id) REFERENCES domain.artifact(artifact_id);
    """)


def downgrade() -> None:
    """路径事实和投影通过审核的前向迁移维护。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
