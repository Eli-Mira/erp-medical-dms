"""alembic revision script for adding performance indexes."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0024_perf_indexes"
down_revision = "0023_audit_append_only"
branch_labels = None
depends_on = None


def upgrade():
    # sales schema indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_invoice_status_date "
        "ON sales.sales_invoice (posting_status, invoice_date DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_invoice_territory_date "
        "ON sales.sales_invoice (territory_id, invoice_date DESC)"
    )

    # finance schema indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ar_entry_customer_date "
        "ON finance.ar_entry (customer_id, entry_date DESC, id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ar_entry_date_due "
        "ON finance.ar_entry (entry_date, due_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_payment_receipt_invoice_status "
        "ON finance.payment_receipt (invoice_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_payment_receipt_date_id "
        "ON finance.payment_receipt (receipt_date DESC, id)"
    )

    # audit schema indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_created_at "
        "ON audit.audit_log (created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_entity "
        "ON audit.audit_log (entity_type, entity_id)"
    )


def downgrade():
    # sales schema indexes
    op.execute("DROP INDEX IF EXISTS sales.ix_sales_invoice_status_date")
    op.execute("DROP INDEX IF EXISTS sales.ix_sales_invoice_territory_date")

    # finance schema indexes
    op.execute("DROP INDEX IF EXISTS finance.ix_ar_entry_customer_date")
    op.execute("DROP INDEX IF EXISTS finance.ix_ar_entry_date_due")
    op.execute("DROP INDEX IF EXISTS finance.ix_payment_receipt_invoice_status")
    op.execute("DROP INDEX IF EXISTS finance.ix_payment_receipt_date_id")

    # audit schema indexes
    op.execute("DROP INDEX IF EXISTS audit.ix_audit_log_created_at")
    op.execute("DROP INDEX IF EXISTS audit.ix_audit_log_entity")
