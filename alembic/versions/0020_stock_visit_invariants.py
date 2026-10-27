"""Backstop S7 nullable held-stock identity and visit quantity/batch invariants.

Duplicate existing NULL-batch records or invalid observations fail migration;
no historical row is silently selected, deleted, or reconciled.
"""

from alembic import op

revision = "0020_stock_visit_invariants"
down_revision = "0019_held_stock_fk_set_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales.customer_held_stock
            DROP CONSTRAINT customer_held_stock_customer_id_product_id_batch_id_key,
            ADD CONSTRAINT uq_customer_held_stock_tuple
                UNIQUE NULLS NOT DISTINCT (customer_id, product_id, batch_id),
            ADD CONSTRAINT fk_held_stock_product_batch
                FOREIGN KEY (batch_id, product_id)
                REFERENCES inventory.batch_record(id, product_id);
        ALTER TABLE sales.customer_stock_visit_line
            ADD CONSTRAINT fk_visit_line_product_batch
                FOREIGN KEY (batch_id, product_id)
                REFERENCES inventory.batch_record(id, product_id),
            ADD CONSTRAINT ck_visit_sell_through_nonnegative CHECK (sell_through >= 0);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE sales.customer_stock_visit_line
            DROP CONSTRAINT ck_visit_sell_through_nonnegative,
            DROP CONSTRAINT fk_visit_line_product_batch;
        ALTER TABLE sales.customer_held_stock
            DROP CONSTRAINT fk_held_stock_product_batch,
            DROP CONSTRAINT uq_customer_held_stock_tuple,
            ADD CONSTRAINT customer_held_stock_customer_id_product_id_batch_id_key
                UNIQUE (customer_id, product_id, batch_id);
    """)
