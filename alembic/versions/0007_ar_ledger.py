"""Finance schema: customer receivables ledger (Module E, AR half).

Minimal AR ledger honoring the Excel العملاء convention:
  debit = مدين (increases balance / money the customer owes),
  credit = دائن (decreases balance / customer pays),
  balance = Σ(debit) − Σ(credit) per customer (D23).

'sale'/'return'/'transfer_*' movement types belong to stock; AR 'invoice'
entry type is reserved for the (disabled) posting flow and is not API-writable.
"""
from alembic import op

revision = "0007_ar_ledger"
down_revision = "0006_inventory_ar_gate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE SCHEMA IF NOT EXISTS finance;
        CREATE TABLE finance.ar_entry (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES master_data.master_customer(id),
            invoice_id uuid REFERENCES sales.sales_invoice(id),
            entry_type varchar(20) NOT NULL,
            entry_date date NOT NULL,
            due_date date,
            debit numeric(14,2) NOT NULL DEFAULT 0,
            credit numeric(14,2) NOT NULL DEFAULT 0,
            reason_id uuid REFERENCES audit.reason_code(id),
            note text,
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_ar_amounts_nonneg CHECK (debit >= 0 AND credit >= 0),
            CONSTRAINT ck_ar_one_side CHECK (debit > 0 OR credit > 0),
            CONSTRAINT ck_ar_types CHECK (entry_type IN
                ('opening', 'invoice', 'payment', 'credit_note', 'adjustment')),
            CONSTRAINT ck_ar_invoice_only_for_invoice_type
                CHECK (invoice_id IS NOT NULL OR entry_type != 'invoice')
        );
        CREATE INDEX ix_ar_entry_customer ON finance.ar_entry(customer_id);
        CREATE INDEX ix_ar_entry_type ON finance.ar_entry(entry_type);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX finance.ix_ar_entry_type;
        DROP INDEX finance.ix_ar_entry_customer;
        DROP TABLE finance.ar_entry;
        DROP SCHEMA IF EXISTS finance;
    """)
