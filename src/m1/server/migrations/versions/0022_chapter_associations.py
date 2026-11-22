"""建立章节对任务及方法的精确选择。"""

from alembic import op

revision = "0022_chapter_associations"
down_revision = "0021_domain_intake_processing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE product.chapter_association (
            association_id uuid PRIMARY KEY,
            textbook_id uuid NOT NULL REFERENCES product.textbook(textbook_id),
            chapter_id uuid NOT NULL REFERENCES product.material_chapter(chapter_id),
            task_id uuid NOT NULL,
            task_version bigint NOT NULL CHECK (task_version > 0),
            method_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
            revision bigint NOT NULL CHECK (revision>0),
            active boolean NOT NULL DEFAULT true,
            last_event_ref uuid NOT NULL,
            updated_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE UNIQUE INDEX uq_chapter_active_task
            ON product.chapter_association(chapter_id,task_id) WHERE active;
        CREATE INDEX ix_chapter_association_event ON product.chapter_association(source_event_id);
        GRANT SELECT, INSERT ON product.chapter_association TO deermind_app;
        GRANT UPDATE (task_version,method_refs,revision,active,last_event_ref,updated_at,
            source_event_id)
            ON product.chapter_association TO deermind_app;
    """)


def downgrade() -> None:
    """章节选择及历史事实必须保留。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
