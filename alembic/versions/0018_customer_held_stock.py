"""Customer-held stock (sell-through) persistence (V2 §2B.9).

V2 §2B.9: Sell-through means quantity actually sold/moved by the customer from
the stock held at that customer. Sell-through must not be inferred from
sell-in alone.

This table tracks the running customer-held stock balance per (customer,
product, batch). It is updated by the visit workflow (V2 §2B.10):
- quantity_prev is the opening balance before the visit
- quantity_delivered increases customer-held stock
- quantity_returned decreases customer-held stock
- quantity_current is the closing balance after the visit
- sell_through = prev + delivered - returned - current (validated by visit CHECK)

The customer-held balance is the running total of:
  sold_through (out) + returns_from_customer (in) + adjustments

This is an operational balance, not a posted financial ledger.
"""
from alembic import op

revision = "0018_customer_held_stock"
down_revision = "0017_customer_stock_visit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE sales.customer_held_stock (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id uuid NOT NULL REFERENCES master_data.master_customer(id),
            product_id uuid NOT NULL REFERENCES master_data.master_product(id),
            batch_id uuid REFERENCES inventory.batch_record(id),
            quantity_on_hand numeric(12,3) NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
            last_visit_id uuid REFERENCES sales.customer_stock_visit(id),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (customer_id, product_id, batch_id)
        );
        CREATE INDEX ix_customer_held_customer
            ON sales.customer_held_stock(customer_id);
        CREATE INDEX ix_customer_held_product
            ON sales.customer_held_stock(product_id);
        """
    )


def downgrade() -> None:
    from sqlalchemy import text

    used = op.get_bind().execute(
        text("SELECT EXISTS(SELECT 1 FROM sales.customer_held_stock)")
    ).scalar_one()
    if used:
        raise RuntimeError(
            "Cannot downgrade: customer held stock records must be preserved"
        )
    op.execute("DROP TABLE sales.customer_held_stock;")