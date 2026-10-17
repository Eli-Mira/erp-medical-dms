"""Branch -> warehouse fulfillment compatibility (not an inventory access grant).

Dakahlia and Sharqia use Dakahlia; Gharbia may use Dakahlia or Gharbia.
Inventory access instead follows explicit platform.user_branch grants joined to
master_warehouse.branch_id. Routing alone must never widen that scope.
"""
from alembic import op

revision = "0008_branch_warehouse"
down_revision = "0007_ar_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE inventory.branch_warehouse (
            branch_id UUID NOT NULL,
            warehouse_id UUID NOT NULL,
            PRIMARY KEY (branch_id, warehouse_id),
            FOREIGN KEY (branch_id) REFERENCES master_data.master_branch(id),
            FOREIGN KEY (warehouse_id) REFERENCES master_data.master_warehouse(id)
        );
        CREATE INDEX ix_inventory_branch_warehouse_branch_id
            ON inventory.branch_warehouse (branch_id);
        CREATE INDEX ix_inventory_branch_warehouse_warehouse_id
            ON inventory.branch_warehouse (warehouse_id);
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_inventory_branch_warehouse_warehouse_id")
    op.execute("DROP INDEX IF EXISTS ix_inventory_branch_warehouse_branch_id")
    op.execute("DROP TABLE IF EXISTS inventory.branch_warehouse")
