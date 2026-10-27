"""Customer stock-visit persistence (V2 §2B.10, §2B.11).

Previously the field follow-up workflow (the paper customer-stock form) existed
only as a browser prototype storing rows in localStorage. This migration makes
it real: a visit is one field call (rep + customer + date + notes) carrying one
line per product, with the sell-through formula enforced as a table CHECK so it
cannot be silently violated by any caller.

Sell-through = prev + delivered - returned - current  (V2 §2B.11).

Transfers, invoices and AR are untouched. Visits are operational records, not
posted financial transactions: they are hard-deletable (like drafts) but every
create/delete is written to the immutable audit log.
"""
from alembic import op

revision = "0017_customer_stock_visit"
down_revision = "0016_customer_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sales.customer_stock_visit (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES master_data.master_customer(id),
            rep_id uuid NOT NULL REFERENCES platform.platform_user(id),
            visit_date date NOT NULL,
            notes text,
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_visit_customer_date
            ON sales.customer_stock_visit(customer_id, visit_date);
        CREATE INDEX ix_visit_rep_date
            ON sales.customer_stock_visit(rep_id, visit_date);

        CREATE TABLE sales.customer_stock_visit_line (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            visit_id uuid NOT NULL REFERENCES sales.customer_stock_visit(id)
                ON DELETE CASCADE,
            product_id uuid NOT NULL REFERENCES master_data.master_product(id),
            batch_id uuid REFERENCES inventory.batch_record(id),
            quantity_prev numeric(12,3) NOT NULL DEFAULT 0
                CHECK (quantity_prev >= 0),
            quantity_delivered numeric(12,3) NOT NULL DEFAULT 0
                CHECK (quantity_delivered >= 0),
            quantity_returned numeric(12,3) NOT NULL DEFAULT 0
                CHECK (quantity_returned >= 0),
            quantity_current numeric(12,3) NOT NULL DEFAULT 0
                CHECK (quantity_current >= 0),
            sell_through numeric(12,3) NOT NULL
                CHECK (sell_through = quantity_prev + quantity_delivered
                                        - quantity_returned - quantity_current),
            amount numeric(14,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
            payment_method varchar(30),
            notes text
        );
        CREATE UNIQUE INDEX uq_visit_line_product
            ON sales.customer_stock_visit_line(visit_id, product_id);
        CREATE INDEX ix_visit_line_visit
            ON sales.customer_stock_visit_line(visit_id);
        """
    )


def downgrade() -> None:
    from sqlalchemy import text

    used_visit = op.get_bind().execute(
        text("SELECT EXISTS(SELECT 1 FROM sales.customer_stock_visit_line)")
    ).scalar_one()
    used_line = op.get_bind().execute(
        text("SELECT EXISTS(SELECT 1 FROM sales.customer_stock_visit)")
    ).scalar_one()
    if used_visit or used_line:
        raise RuntimeError(
            "Cannot downgrade: customer stock-visit records must be preserved"
        )
    op.execute("DROP TABLE sales.customer_stock_visit_line;")
    op.execute("DROP TABLE sales.customer_stock_visit;")