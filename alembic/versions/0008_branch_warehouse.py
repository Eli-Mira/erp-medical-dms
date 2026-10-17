"""Add the branch -> warehouse access mapping used for least-privilege inventory
authorization. A warehouse can serve multiple branches (Sharqia and Dakahlia
share the Dakahlia warehouse; Gharbia can use the Dakahlia or Gharbia
warehouse). master_warehouse.branch_id stays the canonical ownership and is
unambiguously *not* used to scope access - scoping is done through this table
plus platform.user_branch."""
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
