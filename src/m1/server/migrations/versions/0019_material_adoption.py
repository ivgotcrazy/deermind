"""保存候选采用决定、正式目录及当前内容索引。"""

from alembic import op

revision = "0019_material_adoption"
down_revision = "0018_material_corrections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE product.material_adoption (
            decision_id uuid PRIMARY KEY,
            batch_id uuid NOT NULL REFERENCES product.material_candidate_batch(batch_id),
            batch_revision bigint NOT NULL CHECK (batch_revision>0),
            decision text NOT NULL CHECK (decision IN ('adopt','decline')),
            actor_ref jsonb NOT NULL,
            before_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            after_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            impact jsonb NOT NULL,
            request_ref uuid NOT NULL REFERENCES product.command_receipt(request_ref),
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE (batch_id,batch_revision)
        );
        CREATE TABLE product.material_chapter (
            chapter_id uuid PRIMARY KEY,
            textbook_id uuid NOT NULL REFERENCES product.textbook(textbook_id),
            parent_id uuid REFERENCES product.material_chapter(chapter_id),
            title text NOT NULL CHECK (length(btrim(title))>0),
            sort_order bigint NOT NULL CHECK (sort_order>=0),
            page_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            revision bigint NOT NULL CHECK (revision>0),
            catalog_basis_ref jsonb NOT NULL,
            updated_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE TABLE product.material_content_current (
            import_id uuid NOT NULL REFERENCES product.material_import(import_id),
            candidate_id uuid NOT NULL,
            candidate_revision bigint NOT NULL,
            chapter_id uuid NOT NULL REFERENCES product.material_chapter(chapter_id),
            validity text NOT NULL CHECK (validity IN ('current','requires_review','retired')),
            adoption_ref uuid NOT NULL REFERENCES product.material_adoption(decision_id),
            PRIMARY KEY(import_id,candidate_id),
            FOREIGN KEY(candidate_id,candidate_revision)
                REFERENCES product.material_candidate(candidate_id,candidate_revision)
        );
        CREATE INDEX ix_material_adoption_event ON product.material_adoption(source_event_id);
        CREATE INDEX ix_material_chapter_event ON product.material_chapter(source_event_id);
        CREATE INDEX ix_material_chapter_book ON product.material_chapter(textbook_id,chapter_id);
        CREATE INDEX ix_material_current_chapter
            ON product.material_content_current(import_id,chapter_id,validity,candidate_id);
        GRANT SELECT, INSERT ON product.material_adoption, product.material_chapter,
            product.material_content_current TO deermind_app;
        GRANT UPDATE (title,sort_order,page_refs,revision,catalog_basis_ref,
            updated_at,source_event_id)
            ON product.material_chapter TO deermind_app;
        GRANT UPDATE (candidate_revision,chapter_id,validity,adoption_ref)
            ON product.material_content_current TO deermind_app;
        GRANT UPDATE (content_revision) ON product.material_import TO deermind_app;
    """)


def downgrade() -> None:
    """教材采用和目录历史随前向迁移保留。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
