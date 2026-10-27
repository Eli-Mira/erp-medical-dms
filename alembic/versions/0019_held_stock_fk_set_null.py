"""Make customer_held_stock.last_visit_id FK SET NULL on visit delete (V2 §2B.9).

The visit deletion was blocked by the FK constraint. Since visits are operational
records that can be hard-deleted (like drafts), the held stock reference should
be set to NULL rather than blocking the deletion.
"""

from alembic import op

revision = "0019_held_stock_fk_set_null"
down_revision = "0018_customer_held_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sales.customer_held_stock
        DROP CONSTRAINT customer_held_stock_last_visit_id_fkey,
        ADD CONSTRAINT customer_held_stock_last_visit_id_fkey
            FOREIGN KEY (last_visit_id)
            REFERENCES sales.customer_stock_visit(id)
            ON DELETE SET NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sales.customer_held_stock
        DROP CONSTRAINT customer_held_stock_last_visit_id_fkey,
        ADD CONSTRAINT customer_held_stock_last_visit_id_fkey
            FOREIGN KEY (last_visit_id)
            REFERENCES sales.customer_stock_visit(id)
        """
    )
