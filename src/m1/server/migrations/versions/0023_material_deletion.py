"""授予教材软删除列权限，业务版本和原件保留。"""

from alembic import op

revision = "0023_material_deletion"
down_revision = "0022_chapter_associations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT UPDATE (status) ON product.material_import TO deermind_app")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (status) ON product.material_import FROM deermind_app")
