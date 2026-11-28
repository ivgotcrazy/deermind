"""Keep teaching definitions with their book edition and publish assessment sets atomically."""

from alembic import op

revision = "0044_book_models"
down_revision = "0043_material_editions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        GRANT DELETE ON product.material_source TO deermind_app;
        ALTER TABLE product.material_edition ADD COLUMN teaching jsonb;
        CREATE TABLE evaluation.assessment_model (
            model_id uuid PRIMARY KEY,
            extraction_id uuid NOT NULL REFERENCES product.material_edition,
            name text NOT NULL CHECK (length(trim(name))>0),
            number integer NOT NULL CHECK(number>0),
            revision integer NOT NULL CHECK(revision>0),
            status text NOT NULL CHECK(status IN ('draft','published')),
            claims jsonb NOT NULL CHECK(jsonb_typeof(claims)='array'),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (extraction_id,number),
            UNIQUE (extraction_id,model_id)
        );
        ALTER TABLE evaluation.claim DROP CONSTRAINT claim_task_id_task_version_key;
        ALTER TABLE evaluation.claim ADD COLUMN model_id uuid
            REFERENCES evaluation.assessment_model;
        CREATE UNIQUE INDEX claim_unbound_task ON evaluation.claim(task_id,task_version)
            WHERE model_id IS NULL;
        CREATE UNIQUE INDEX claim_member_task ON evaluation.claim(model_id,task_id,task_version)
            WHERE model_id IS NOT NULL;
        ALTER TABLE product.learning_target_version ADD COLUMN assessment_id uuid;
        ALTER TABLE product.learning_target_version ADD FOREIGN KEY (extraction_id,assessment_id)
            REFERENCES evaluation.assessment_model(extraction_id,model_id);
        GRANT SELECT,INSERT,UPDATE ON evaluation.assessment_model TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Use a forward migration for published models")
