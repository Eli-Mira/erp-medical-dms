"""Inventory stock ledger + balances (Module D, first slice).

Movement rows are the append-only ledger (APP_FLOW §5 D1); the balance row is
the running total per (warehouse, product, batch) (D2). Stock cover, overstock
and low-stock thresholds are deliberately NOT part of this migration.

Invoice posting stays disabled: this slice adds the stock half only. The
customer-receivables half and the atomic posting flow are still to come.
"""
from alembic import op

revision = "0005_inventory_stock"
down_revision = "0004_invoice_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE inventory.batch_record
            ADD CONSTRAINT uq_batch_record_warehouse UNIQUE (id, warehouse_id);

        CREATE TABLE inventory.stock_movement (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            warehouse_id uuid NOT NULL REFERENCES master_data.master_warehouse(id),
            product_id uuid NOT NULL REFERENCES master_data.master_product(id),
            batch_id uuid,
            movement_type varchar(20) NOT NULL,
            quantity numeric(12,3) NOT NULL,
            unit_cost numeric(12,2),
            source_type varchar(30),
            source_id uuid,
            note text,
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_stock_movement_quantity CHECK (quantity <> 0),
            CONSTRAINT ck_stock_movement_cost CHECK (unit_cost IS NULL OR unit_cost >= 0),
            CONSTRAINT ck_stock_movement_source CHECK (source_id IS NULL OR source_type IS NOT NULL),
            CONSTRAINT ck_stock_movement_type CHECK (movement_type IN
                ('opening', 'receipt', 'sale', 'return', 'transfer_in', 'transfer_out', 'adjustment')),
            CONSTRAINT fk_stock_movement_batch FOREIGN KEY (batch_id, product_id)
                REFERENCES inventory.batch_record(id, product_id),
            CONSTRAINT fk_stock_movement_batch_warehouse FOREIGN KEY (batch_id, warehouse_id)
                REFERENCES inventory.batch_record(id, warehouse_id)
        );

        CREATE TABLE inventory.stock_balance (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            warehouse_id uuid NOT NULL REFERENCES master_data.master_warehouse(id),
            product_id uuid NOT NULL REFERENCES master_data.master_product(id),
            batch_id uuid,
            quantity numeric(14,3) NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_stock_balance_nonneg CHECK (quantity >= 0),
            CONSTRAINT fk_stock_balance_batch FOREIGN KEY (batch_id, product_id)
                REFERENCES inventory.batch_record(id, product_id),
            CONSTRAINT fk_stock_balance_batch_warehouse FOREIGN KEY (batch_id, warehouse_id)
                REFERENCES inventory.batch_record(id, warehouse_id)
        );

        CREATE UNIQUE INDEX uq_stock_balance_batch ON inventory.stock_balance(warehouse_id, product_id, batch_id)
            WHERE batch_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_stock_balance_nobatch ON inventory.stock_balance(warehouse_id, product_id)
            WHERE batch_id IS NULL;
        CREATE INDEX ix_stock_movement_lookup ON inventory.stock_movement(warehouse_id, product_id, created_at DESC);
        CREATE INDEX ix_stock_movement_batch ON inventory.stock_movement(batch_id);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX inventory.ix_stock_movement_batch;
        DROP INDEX inventory.ix_stock_movement_lookup;
        DROP INDEX inventory.uq_stock_balance_nobatch;
        DROP INDEX inventory.uq_stock_balance_batch;
        DROP TABLE inventory.stock_balance;
        DROP TABLE inventory.stock_movement;
        ALTER TABLE inventory.batch_record DROP CONSTRAINT uq_batch_record_warehouse;
    """)
