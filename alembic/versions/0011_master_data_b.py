"""B Master Data slice: supplier, minimal chart of accounts, doctor/KOL master.

Confirmed requirements only (no invented accounting/business policy):

- ``master_data.master_supplier`` — PRD B-02 / G-01 (D11: real purchasing
  activity exists; PO/GRN depth stays discovery-gated). Planning column
  ``status`` is realized as the implemented ``is_active`` soft-delete flag
  used by every other master table (DATABASE_SCHEMA §13).
- ``finance.coa_account`` — PRD B-12 / E-05: "minimal COA supporting AR, AP,
  Cash, Revenue, Expense, Assets". Only the five fundamental accounting types
  are constrained; no account codes or names are seeded because the workbook
  evidence contains a P&L/BS structure, not a coded chart of accounts.
- ``marketing.marketing_kol`` — PRD B-13 (D22: ``حسابات خاصه.xlsx::Sheet1`` is
  the doctor/KOL list). Specialty stays an inline attribute (no specialty
  master table exists in the authoritative schema).

No UOM tables: box/pack/unit conversion stays gated (D13/D20) until real
operations confirm it. No real supplier/doctor/financial records are loaded —
this migration creates structure only.
"""

from alembic import op

revision = "0011_master_data_b"
down_revision = "0010_invoice_collections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE master_data.master_supplier (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code varchar(30) NOT NULL UNIQUE,
            name_ar varchar(200) NOT NULL,
            name_en varchar(200),
            contact_phone varchar(30),
            address text,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_supplier_code CHECK (code ~ '[^[:space:]]')
        );

        CREATE TABLE finance.coa_account (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code varchar(20) NOT NULL UNIQUE,
            name_ar varchar(200) NOT NULL,
            name_en varchar(200),
            account_type varchar(20) NOT NULL,
            parent_id uuid REFERENCES finance.coa_account(id),
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_coa_account_type CHECK (
                account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')),
            CONSTRAINT ck_coa_parent_not_self CHECK (parent_id IS NULL OR parent_id <> id)
        );
        CREATE INDEX ix_coa_parent ON finance.coa_account(parent_id);

        CREATE SCHEMA IF NOT EXISTS marketing;
        CREATE TABLE marketing.marketing_kol (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code varchar(30) NOT NULL UNIQUE,
            name_ar varchar(200) NOT NULL,
            name_en varchar(200),
            specialty varchar(100),
            branch_id uuid REFERENCES master_data.master_branch(id),
            contact_phone varchar(30),
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_kol_code CHECK (code ~ '[^[:space:]]')
        );
        CREATE INDEX ix_kol_branch ON marketing.marketing_kol(branch_id);
        """
    )


def downgrade() -> None:
    # Only the tables this migration created are dropped. The empty ``marketing``
    # schema is left in place: ``CREATE SCHEMA IF NOT EXISTS`` makes re-upgrade
    # idempotent, and dropping a schema this migration does not own could destroy
    # objects created out-of-band (a future migration that adds marketing tables
    # would also fail its own downgrade here).
    op.execute(
        """
        DROP TABLE marketing.marketing_kol;
        DROP TABLE finance.coa_account;
        DROP TABLE master_data.master_supplier;
        """
    )
