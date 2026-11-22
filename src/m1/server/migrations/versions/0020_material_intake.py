"""建立教材提交与领域待入库记录。"""

from alembic import op

revision = "0020_material_intake"
down_revision = "0019_material_adoption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE product.material_intake_submission (
            submission_id uuid PRIMARY KEY,
            import_id uuid NOT NULL REFERENCES product.material_import(import_id),
            candidate_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            parent_bindings jsonb NOT NULL,
            trigger_event_id uuid NOT NULL UNIQUE,
            status text NOT NULL CHECK (status IN ('submitted','received','rejected')),
            domain_receipt_ref jsonb,
            wait_state text NOT NULL CHECK (wait_state IN ('waiting','timed_out','closed')),
            items jsonb NOT NULL DEFAULT '[]'::jsonb,
            issues jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE domain.intake_submission (
            submission_id uuid PRIMARY KEY,
            trigger_event_id uuid NOT NULL UNIQUE,
            domain_id uuid NOT NULL REFERENCES domain.object_identity(object_id),
            product_submission_ref jsonb NOT NULL,
            input_artifact_id uuid NOT NULL REFERENCES domain.artifact(artifact_id),
            outcome text NOT NULL CHECK (outcome IN ('received','rejected')),
            item_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            issues jsonb NOT NULL DEFAULT '[]'::jsonb,
            decision_event_id uuid NOT NULL,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE domain.intake_item (
            item_id uuid PRIMARY KEY,
            domain_id uuid NOT NULL REFERENCES domain.object_identity(object_id),
            candidate_key text NOT NULL,
            source_ref jsonb NOT NULL,
            input_artifact_id uuid NOT NULL REFERENCES domain.artifact(artifact_id),
            kind text NOT NULL CHECK (kind IN ('kc','task_instance','reference')),
            title text NOT NULL CHECK (length(btrim(title))>0),
            group_id uuid NOT NULL,
            parent_item_id uuid REFERENCES domain.intake_item(item_id),
            parent_instance_ref jsonb,
            state text NOT NULL CHECK (state IN ('pending','completed','removed')),
            revision bigint NOT NULL CHECK (revision>0),
            result_ref jsonb,
            processed_request_ref uuid REFERENCES domain.command_receipt(receipt_id),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (domain_id,candidate_key),
            CHECK (
                (kind='reference' AND num_nonnulls(parent_item_id,parent_instance_ref)=1)
                OR (kind<>'reference' AND parent_item_id IS NULL AND parent_instance_ref IS NULL)
            )
        );
        CREATE INDEX ix_product_intake_import
            ON product.material_intake_submission(import_id,submission_id);
        CREATE INDEX ix_product_intake_event
            ON product.material_intake_submission(source_event_id);
        CREATE INDEX ix_domain_intake_submission_event ON domain.intake_submission(source_event_id);
        CREATE INDEX ix_domain_intake_state ON domain.intake_item(domain_id,state,item_id);
        CREATE INDEX ix_domain_intake_event ON domain.intake_item(source_event_id);
        CREATE INDEX ix_domain_intake_parent ON domain.intake_item(parent_item_id);
        GRANT SELECT, INSERT ON product.material_intake_submission,domain.intake_submission,
            domain.intake_item TO deermind_app;
        GRANT UPDATE (status,domain_receipt_ref,wait_state,items,issues,source_event_id)
            ON product.material_intake_submission TO deermind_app;
    """)


def downgrade() -> None:
    """教材到领域的提交及受理记录仅通过前向迁移维护。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
