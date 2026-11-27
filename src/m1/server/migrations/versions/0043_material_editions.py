"""Version the textbook tree independently from each published teaching extraction."""

from alembic import op

revision = "0043_material_editions"
down_revision = "0042_fixed_space_course"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE product.material_edition (
            edition_id uuid PRIMARY KEY,
            textbook_id uuid NOT NULL REFERENCES product.textbook,
            kind text NOT NULL CHECK (kind IN ('tree','extraction')),
            number integer NOT NULL CHECK (number > 0),
            tree_id uuid,
            status text NOT NULL CHECK (status IN ('draft','published','discarded')),
            revision integer NOT NULL CHECK (revision > 0),
            pages jsonb NOT NULL CHECK (jsonb_typeof(pages)='array'),
            entries jsonb NOT NULL CHECK (jsonb_typeof(entries)='array'),
            pending jsonb,
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL,
            UNIQUE(textbook_id,kind,number),
            UNIQUE(textbook_id,edition_id),
            FOREIGN KEY(textbook_id,tree_id)
                REFERENCES product.material_edition(textbook_id,edition_id),
            CHECK ((kind='tree')=(tree_id IS NULL))
        );
        CREATE TABLE product.material_content_node (
            material_version_id uuid NOT NULL REFERENCES product.material_edition(edition_id),
            node_id uuid NOT NULL,
            parent_id uuid,
            node_kind text NOT NULL CHECK (node_kind IN
                ('book','unit','chapter','section','group','example','exercise','subquestion',
                 'solution','heading','paragraph','caption','formula','table','chart','diagram','image')),
            sibling_order integer NOT NULL CHECK (sibling_order > 0),
            content jsonb CHECK (jsonb_typeof(content)='object'),
            covered_page_ids uuid[] NOT NULL,
            PRIMARY KEY(material_version_id,node_id),
            FOREIGN KEY(material_version_id,parent_id)
                REFERENCES product.material_content_node(material_version_id,node_id)
                DEFERRABLE INITIALLY DEFERRED,
            UNIQUE(material_version_id,parent_id,sibling_order),
            CHECK ((parent_id IS NULL)=(node_kind='book') AND parent_id IS DISTINCT FROM node_id),
            CHECK (array_position(covered_page_ids,NULL) IS NULL)
        );
        CREATE UNIQUE INDEX material_tree_root ON product.material_content_node(material_version_id)
            WHERE parent_id IS NULL;
        CREATE INDEX material_node_pages ON product.material_content_node
            USING gin(covered_page_ids);
        ALTER TABLE product.learning_target_version ADD COLUMN extraction_id uuid
            REFERENCES product.material_edition(edition_id);
        GRANT SELECT,INSERT,UPDATE ON product.material_edition TO deermind_app;
        GRANT SELECT,INSERT,DELETE ON product.material_content_node TO deermind_app;
    """)


def downgrade() -> None:
    raise RuntimeError("Retain published textbook versions through a forward migration.")
