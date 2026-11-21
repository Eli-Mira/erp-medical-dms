from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "0025_returns_accounting"
down_revision = "0024_perf_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE sales.sales_return
            DROP CONSTRAINT sales_return_status_check,
            ADD CONSTRAINT sales_return_status_check
                CHECK (status IN ('recorded', 'quarantined', 'approved', 'approved_restock', 'scrapped', 'rejected')),
            ADD COLUMN unit_price numeric(12,2) CHECK (unit_price IS NULL OR unit_price >= 0),
            ADD COLUMN vat_rate numeric(5,2) CHECK (vat_rate IS NULL OR vat_rate IN (0, 14)),
            ADD COLUMN net_credit numeric(14,2) CHECK (net_credit IS NULL OR net_credit >= 0),
            ADD COLUMN vat_reversal numeric(14,2) CHECK (vat_reversal IS NULL OR vat_reversal >= 0),
            ADD COLUMN gross_credit numeric(14,2) CHECK (gross_credit IS NULL OR gross_credit >= 0),
            ADD COLUMN restock_movement_id uuid REFERENCES inventory.stock_movement(id),
            ADD COLUMN credit_note_entry_id uuid REFERENCES finance.ar_entry(id),
            ADD COLUMN decided_by uuid REFERENCES platform.platform_user(id),
            ADD COLUMN decided_at timestamptz,
            ADD COLUMN decision_note text;
        CREATE UNIQUE INDEX uq_sales_return_restock_mv
            ON sales.sales_return(restock_movement_id)
            WHERE restock_movement_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_sales_return_credit_ar
            ON sales.sales_return(credit_note_entry_id)
            WHERE credit_note_entry_id IS NOT NULL;
        """
    )


def downgrade():
    bind = op.get_bind()
    result = bind.execute(
        text(
            "SELECT EXISTS(SELECT 1 FROM sales.sales_return WHERE decided_at IS NOT NULL OR status IN ('approved_restock', 'scrapped'))"
        )
    ).scalar_one()
    if result:
        raise RuntimeError(
            "Cannot downgrade: returns accounting history must be preserved"
        )
    op.execute(
        """
        DROP INDEX IF EXISTS sales.uq_sales_return_restock_mv;
        DROP INDEX IF EXISTS sales.uq_sales_return_credit_ar;
        ALTER TABLE sales.sales_return
            DROP CONSTRAINT sales_return_status_check,
            ADD CONSTRAINT sales_return_status_check
                CHECK (status IN ('recorded', 'approved', 'rejected', 'quarantined')),
            DROP COLUMN unit_price,
            DROP COLUMN vat_rate,
            DROP COLUMN net_credit,
            DROP COLUMN vat_reversal,
            DROP COLUMN gross_credit,
            DROP COLUMN restock_movement_id,
            DROP COLUMN credit_note_entry_id,
            DROP COLUMN decided_by,
            DROP COLUMN decided_at,
            DROP COLUMN decision_note;
        """
    )
