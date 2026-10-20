"""Private/owner accounts: isolated protected module (D40).

Same PostgreSQL database, separate schema, owner-only access, separate audit.
No company AR/stock code paths are shared. Lightweight ledger entry model
mirrors the workbook's partner/project/property/expense accounts without
inventing accounting policy.
"""
from alembic import op

revision = "0015_private_accounts"
down_revision = "0014_marketing_spend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE SCHEMA IF NOT EXISTS private;
        CREATE TABLE private.account_entry (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            account_label varchar(120) NOT NULL,
            entry_date date NOT NULL,
            debit numeric(14,2) NOT NULL DEFAULT 0 CHECK (debit >= 0),
            credit numeric(14,2) NOT NULL DEFAULT 0 CHECK (credit >= 0),
            note text,
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (debit > 0 OR credit > 0)
        );
        CREATE INDEX ix_private_entry_date ON private.account_entry(entry_date);
        CREATE INDEX ix_private_entry_account ON private.account_entry(account_label);
    """)


def downgrade() -> None:
    from sqlalchemy import text

    used = op.get_bind().execute(
        text("SELECT EXISTS(SELECT 1 FROM private.account_entry)")
    ).scalar_one()
    if used:
        raise RuntimeError(
            "Cannot downgrade: private account records must be preserved"
        )
    # Drop only the table this migration owns; leave the schema in place so
    # out-of-band objects are not destroyed (mirrors 0011).
    op.execute("DROP TABLE private.account_entry;")
