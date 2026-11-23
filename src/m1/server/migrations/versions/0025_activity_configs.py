"""建立活动定义修订、解析包和当前指针。"""

from alembic import op

revision = "0025_activity_configs"
down_revision = "0024_claim_definitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for kind in ("blueprint", "rule", "strategy", "binding"):
        op.execute(f"""
            CREATE TABLE interaction.{kind}_revisions (
                {kind}_id uuid NOT NULL,
                revision bigint NOT NULL CHECK(revision > 0),
                activity_type text NOT NULL,
                definition jsonb NOT NULL,
                actor_ref jsonb NOT NULL,
                created_at timestamptz NOT NULL,
                source_event_id uuid NOT NULL,
                PRIMARY KEY ({kind}_id,revision)
            );
            CREATE INDEX ix_{kind}_revision_event
                ON interaction.{kind}_revisions(source_event_id);
            GRANT SELECT,INSERT ON interaction.{kind}_revisions TO deermind_app;
        """)
    op.execute("""
        CREATE TABLE interaction.resolved_configs (
            config_id uuid PRIMARY KEY,
            activity_type text NOT NULL,
            blueprint_ref jsonb NOT NULL,
            binding_ref jsonb NOT NULL,
            rule_refs jsonb NOT NULL DEFAULT '[]',
            strategy_refs jsonb NOT NULL DEFAULT '[]',
            created_at timestamptz NOT NULL,
            source_event_id uuid NOT NULL
        );
        CREATE INDEX ix_resolved_config_event ON interaction.resolved_configs(source_event_id);
        CREATE TABLE interaction.config_heads (
            activity_type text PRIMARY KEY,
            config_id uuid NOT NULL REFERENCES interaction.resolved_configs(config_id),
            revision bigint NOT NULL CHECK(revision > 0)
        );
        GRANT SELECT,INSERT ON interaction.resolved_configs,interaction.config_heads
            TO deermind_app;
        GRANT UPDATE (config_id,revision) ON interaction.config_heads TO deermind_app;
    """)


def downgrade() -> None:
    """保留已发布活动配置及采用历史。"""
    raise RuntimeError("Destructive downgrade is not supported; use a reviewed forward migration")
