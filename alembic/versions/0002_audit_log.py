"""Initial audit + reference schema (P2.6 audit, P2.9 reason codes).

Matches DATABASE_SCHEMA.md section 10 exactly:
  - audit.audit_log  (immutable, actor FK→platform_user, NO DELETE in app)
  - audit.reason_code (returns, voids, adjustments — referenced by sales_invoice)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB

# revision identifiers, used by Alembic.
revision = "0002_audit_log"
down_revision = "0001_platform"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("platform.platform_user.id")),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.UUID(as_uuid=True)),
        sa.Column("old_values", JSONB),
        sa.Column("new_values", JSONB),
        sa.Column("ip_address", INET()),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="audit",
    )

    op.create_table(
        "reason_code",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(100)),
        sa.Column("name_en", sa.String(100)),
        sa.Column("category", sa.String(30)),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        schema="audit",
    )


def downgrade() -> None:
    op.drop_table("reason_code", schema="audit")
    op.drop_table("audit_log", schema="audit")
    op.execute("DROP SCHEMA IF EXISTS audit")
