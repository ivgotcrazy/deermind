"""建立教材对话、处理轮和待核对候选。"""

from alembic import op

revision = "0017_material_assistant"
down_revision = "0016_material_receiving"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE product.material_turn (
            request_ref uuid PRIMARY KEY,
            import_id uuid NOT NULL REFERENCES product.material_import(import_id),
            input_digest text NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$'),
            input jsonb NOT NULL CHECK (jsonb_typeof(input)='object'),
            runtime_ref uuid,
            state text NOT NULL CHECK (state IN
                ('accepted','completed','needs_input','failed','cancelled')),
            work_state_ref jsonb,
            result_ref jsonb,
            error jsonb,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE product.material_message (
            message_id uuid PRIMARY KEY,
            import_id uuid NOT NULL REFERENCES product.material_import(import_id),
            seq bigint NOT NULL CHECK (seq>0),
            role text NOT NULL CHECK (role IN ('user','assistant')),
            body jsonb NOT NULL CHECK (jsonb_typeof(body)='array'),
            explicit_refs jsonb NOT NULL DEFAULT '[]'::jsonb
                CHECK (jsonb_typeof(explicit_refs)='array'),
            turn_ref uuid NOT NULL REFERENCES product.material_turn(request_ref),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (import_id,seq)
        );
        CREATE TABLE product.material_candidate_batch (
            batch_id uuid PRIMARY KEY,
            batch_revision bigint NOT NULL CHECK (batch_revision>0),
            turn_ref uuid NOT NULL REFERENCES product.material_turn(request_ref),
            scope jsonb NOT NULL,
            read_set jsonb NOT NULL,
            write_set jsonb NOT NULL,
            coverage jsonb NOT NULL,
            diff_summary jsonb NOT NULL,
            decision_state text NOT NULL CHECK (decision_state IN
                ('pending','adopted','declined','superseded')),
            decision_revision bigint NOT NULL CHECK (decision_revision>0),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE product.material_candidate (
            candidate_id uuid NOT NULL,
            candidate_revision bigint NOT NULL CHECK (candidate_revision>0),
            batch_id uuid NOT NULL REFERENCES product.material_candidate_batch(batch_id),
            import_id uuid NOT NULL REFERENCES product.material_import(import_id),
            local_key text NOT NULL,
            kind text NOT NULL CHECK (kind IN ('kc','task_instance','reference')),
            chapter_ref jsonb NOT NULL,
            body jsonb NOT NULL,
            parent_ref jsonb,
            source_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            basis_revision bigint NOT NULL CHECK (basis_revision>=0),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            PRIMARY KEY (candidate_id,candidate_revision),
            UNIQUE (batch_id,local_key),
            CHECK ((kind='reference')=(parent_ref IS NOT NULL))
        );
        ALTER TABLE product.material_import ADD FOREIGN KEY (active_request_ref)
            REFERENCES product.material_turn(request_ref) DEFERRABLE INITIALLY DEFERRED;
        CREATE INDEX ix_material_turn_event ON product.material_turn(source_event_id);
        CREATE INDEX ix_material_message_event ON product.material_message(source_event_id);
        CREATE INDEX ix_material_batch_event ON product.material_candidate_batch(source_event_id);
        CREATE INDEX ix_material_candidate_event ON product.material_candidate(source_event_id);
        GRANT SELECT, INSERT ON product.material_turn, product.material_message,
            product.material_candidate_batch, product.material_candidate TO deermind_app;
        GRANT UPDATE (state,work_state_ref,result_ref,error,updated_at,source_event_id)
            ON product.material_turn TO deermind_app;
        GRANT UPDATE (active_request_ref,next_message_seq)
            ON product.material_import TO deermind_app;
    """)


def downgrade() -> None:
    """对话原文和已提出候选均随前向迁移保留。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
