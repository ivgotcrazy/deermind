"""Protect definitions owned by an immutable published textbook edition."""

from alembic import op

revision = "0045_edition_owned_members"
down_revision = "0044_book_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE domain.object_identity ADD COLUMN source_edition_id uuid
            REFERENCES product.material_edition(edition_id);
        WITH members AS (
            SELECT e.edition_id, (ref->>'object_id')::uuid AS id
            FROM product.material_edition e
            CROSS JOIN LATERAL jsonb_array_elements(e.entries) entry
            CROSS JOIN LATERAL jsonb_array_elements(
                jsonb_build_array(entry->'task_ref') || (entry->'method_refs') ||
                (entry->'knowledge')) ref
            WHERE e.kind='extraction' AND e.status='published' AND e.teaching IS NOT NULL
        )
        UPDATE domain.object_identity i SET source_edition_id=m.edition_id
        FROM members m WHERE i.object_id=m.id
    """)


def downgrade() -> None:
    raise RuntimeError("Use a forward migration for published definitions")
