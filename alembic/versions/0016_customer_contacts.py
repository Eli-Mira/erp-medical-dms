"""Optional customer contacts (PRD B-01, DATABASE_SCHEMA master_customer)."""

from sqlalchemy import text

from alembic import op

revision = "0016_customer_contacts"
down_revision = "0015_private_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE master_data.master_customer ADD COLUMN contact_phone varchar(30), ADD COLUMN address text"
    )


def downgrade() -> None:
    op.execute("LOCK TABLE master_data.master_customer IN ACCESS EXCLUSIVE MODE")
    populated = (
        op.get_bind()
        .execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM master_data.master_customer WHERE contact_phone IS NOT NULL OR address IS NOT NULL)"
            )
        )
        .scalar_one()
    )
    if populated:
        raise RuntimeError("Cannot downgrade: customer contact data must be preserved")
    op.execute(
        "ALTER TABLE master_data.master_customer DROP COLUMN address, DROP COLUMN contact_phone"
    )
