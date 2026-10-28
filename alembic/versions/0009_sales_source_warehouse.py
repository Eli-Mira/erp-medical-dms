"""Sales source warehouse: decouple invoice branch from source-warehouse owner branch.

sales.sales_invoice drops the composite FK that forced the source warehouse's
owner branch to equal the invoice branch, and anchors the reference to
master_warehouse(id) only. Branch compatibility for sourcing is now enforced
explicitly in app/sales/router.py::_prepare via inventory.branch_warehouse,
not by the foreign key.

"""
from alembic import op

revision = "0009_sales_source_warehouse"
down_revision = "0008_branch_warehouse"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE sales.sales_invoice
            DROP CONSTRAINT fk_invoice_warehouse_branch,
            ADD CONSTRAINT fk_invoice_warehouse_source
                FOREIGN KEY (warehouse_id) REFERENCES master_data.master_warehouse(id)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE sales.sales_invoice
            DROP CONSTRAINT fk_invoice_warehouse_source,
            ADD CONSTRAINT fk_invoice_warehouse_branch FOREIGN KEY (warehouse_id, branch_id)
                REFERENCES master_data.master_warehouse(id, branch_id)
        """
    )