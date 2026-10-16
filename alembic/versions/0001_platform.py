"""Initial platform schema (Phase 2 foundation).

Matches DATABASE_SCHEMA.md section 2 (Platform module) exactly:
platform_user, platform_session, platform_setting.
Money/datetime types and the is_owner owner-boundary flag (D10) preserved.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_platform"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS platform")

    op.create_table(
        "platform_user",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(60), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("role", sa.String(30), nullable=False, server_default="user"),
        sa.Column("is_owner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="platform",
    )

    op.create_table(
        "platform_session",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("platform.platform_user.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("device_info", sa.Text),
        sa.Column("ip_address", sa.INET()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="platform",
    )

    op.create_table(
        "platform_setting",
        sa.Column("key", sa.String(60), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("updated_by", sa.UUID(as_uuid=True),
                  sa.ForeignKey("platform.platform_user.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="platform",
    )


def downgrade() -> None:
    op.drop_table("platform_setting", schema="platform")
    op.drop_table("platform_session", schema="platform")
    op.drop_table("platform_user", schema="platform")
    op.execute("DROP SCHEMA IF EXISTS platform")
