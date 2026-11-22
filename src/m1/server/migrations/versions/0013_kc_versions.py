"""授权应用推进领域目录和对象头，版本行仍只追加。"""

from alembic import op

revision = "0013_kc_versions"
down_revision = "0012_domain_roots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """仅授予派生指针列的更新权限。"""
    op.execute(
        "GRANT UPDATE (head_version,catalog_revision) ON domain.object_identity TO deermind_app"
    )


def downgrade() -> None:
    """结构修正应追加迁移，保留已经提交的版本事实。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
