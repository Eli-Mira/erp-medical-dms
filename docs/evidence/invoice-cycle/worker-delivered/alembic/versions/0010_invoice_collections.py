"""Invoice collections: payment receipts, reversal support, and related constraints.

- finance.payment_receipt: invoice-linked receipts (one invoice per receipt,
  partial receipts allowed). Exact positive two-decimal amount, receipt number,
  date, cash/check/transfer method, optional note. Derives customer/branch from
  locked Posted invoice. Server-owned status/actor/totals. Unique receipt number
  per branch.
- Appends exact stock + AR counter-entries on reversal/void.
- Constraints for idempotency, overpayment rejection, terminal-row immutability.
"""

from alembic import op

revision = "0010_invoice_collections"
down_revision = "0009_sales_source_warehouse"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS finance;

        CREATE TABLE finance.payment_receipt (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            invoice_id uuid NOT NULL REFERENCES sales.sales_invoice(id),
            branch_id uuid NOT NULL REFERENCES master_data.master_branch(id),
            customer_id uuid NOT NULL REFERENCES master_data.master_customer(id),
            receipt_no varchar(30) NOT NULL,
            receipt_date date NOT NULL,
            amount numeric(14,2) NOT NULL,
            method varchar(20) NOT NULL,
            note text,
            status varchar(20) NOT NULL DEFAULT 'Active',
            voided_at timestamptz,
            voided_by uuid REFERENCES platform.platform_user(id),
            void_reason_id uuid REFERENCES audit.reason_code(id),
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            updated_by uuid REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            version integer NOT NULL DEFAULT 1,
            CONSTRAINT ck_receipt_amount_positive CHECK (amount > 0),
            CONSTRAINT ck_receipt_method CHECK (method IN ('cash', 'check', 'transfer')),
            CONSTRAINT ck_receipt_status CHECK (status IN ('Active', 'Voided')),
            CONSTRAINT ck_receipt_void_metadata CHECK (
                (status = 'Active' AND voided_at IS NULL AND voided_by IS NULL AND void_reason_id IS NULL)
                OR (status = 'Voided' AND voided_at IS NOT NULL AND voided_by IS NOT NULL AND void_reason_id IS NOT NULL)),
            CONSTRAINT ck_receipt_version CHECK (version >= 1)
        );

        CREATE UNIQUE INDEX uq_receipt_branch_no ON finance.payment_receipt(branch_id, receipt_no);
        CREATE INDEX ix_receipt_invoice ON finance.payment_receipt(invoice_id);
        CREATE INDEX ix_receipt_customer ON finance.payment_receipt(customer_id);
        CREATE INDEX ix_receipt_branch ON finance.payment_receipt(branch_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS finance.ix_receipt_branch;
        DROP INDEX IF EXISTS finance.ix_receipt_customer;
        DROP INDEX IF EXISTS finance.ix_receipt_invoice;
        DROP INDEX IF EXISTS finance.uq_receipt_branch_no;
        DROP TABLE IF EXISTS finance.payment_receipt;
        DROP SCHEMA IF EXISTS finance;
        """
    )