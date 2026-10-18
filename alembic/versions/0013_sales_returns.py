"""Sales returns: explicit return transactions (V2 §2B.12).

A return is its own row plus an inventory movement of type 'return' that
increases the destination warehouse stock. It never edits an old invoice or
balance silently.
"""
from alembic import op

revision = "0013_sales_returns"
down_revision = "0012_sales_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales.sales_return (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES master_data.master_customer(id),
            product_id uuid NOT NULL REFERENCES master_data.master_product(id),
            warehouse_id uuid NOT NULL REFERENCES master_data.master_warehouse(id),
            batch_id uuid REFERENCES inventory.batch_record(id),
            quantity numeric(12,3) NOT NULL CHECK (quantity > 0),
            return_date date NOT NULL,
            reason text,
            status varchar(20) NOT NULL DEFAULT 'recorded'
                CHECK (status IN ('recorded', 'approved', 'rejected')),
            invoice_id uuid REFERENCES sales.sales_invoice(id),
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_sales_return_customer ON sales.sales_return(customer_id);
        CREATE INDEX ix_sales_return_date ON sales.sales_return(return_date);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE sales.sales_return;")
