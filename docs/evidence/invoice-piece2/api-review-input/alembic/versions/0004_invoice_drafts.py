"""Draft invoice safety, territory scope and minimal warehouse/batch references.

No stock quantities, ledger, receipt, allocation or AR implementation here.
The database posting guard must be deliberately replaced, not toggled by config,
when an atomic stock + AR posting implementation has passed its own gate.
"""
from alembic import op

revision = "0004_invoice_drafts"
down_revision = "0003_invoice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE master_data.master_territory (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            code varchar(20) NOT NULL UNIQUE,
            name_ar varchar(100) NOT NULL,
            name_en varchar(100)
        );
        CREATE TABLE platform.user_territory (
            user_id uuid NOT NULL REFERENCES platform.platform_user(id),
            territory_id uuid NOT NULL REFERENCES master_data.master_territory(id),
            PRIMARY KEY (user_id, territory_id)
        );
        ALTER TABLE master_data.master_customer ADD COLUMN territory_id uuid
            REFERENCES master_data.master_territory(id);
        CREATE TABLE master_data.master_warehouse (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            branch_id uuid NOT NULL REFERENCES master_data.master_branch(id),
            code varchar(30) NOT NULL,
            name_ar varchar(100) NOT NULL,
            name_en varchar(100),
            is_active boolean NOT NULL DEFAULT true,
            UNIQUE (branch_id, code), UNIQUE (id, branch_id)
        );
        CREATE SCHEMA IF NOT EXISTS inventory;
        CREATE TABLE inventory.batch_record (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            product_id uuid NOT NULL REFERENCES master_data.master_product(id),
            warehouse_id uuid NOT NULL REFERENCES master_data.master_warehouse(id),
            batch_no varchar(50) NOT NULL,
            manufacture_date date,
            expiry_date date NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (product_id, warehouse_id, batch_no), UNIQUE (id, product_id),
            CONSTRAINT ck_batch_dates CHECK (manufacture_date IS NULL OR manufacture_date <= expiry_date)
        );
        ALTER TABLE sales.sales_invoice
            ALTER COLUMN branch_id SET NOT NULL,
            ALTER COLUMN customer_id SET NOT NULL,
            ALTER COLUMN warehouse_id SET NOT NULL,
            ALTER COLUMN created_by SET NOT NULL,
            ADD COLUMN territory_id uuid NOT NULL REFERENCES master_data.master_territory(id),
            ADD COLUMN version integer NOT NULL DEFAULT 1,
            ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
            ADD COLUMN updated_by uuid REFERENCES platform.platform_user(id),
            ADD COLUMN voided_by uuid REFERENCES platform.platform_user(id),
            ADD CONSTRAINT fk_invoice_warehouse_branch FOREIGN KEY (warehouse_id, branch_id)
                REFERENCES master_data.master_warehouse(id, branch_id),
            ADD CONSTRAINT ck_invoice_posting_disabled CHECK (
                posting_status IN ('Draft', 'Voided') AND posted_at IS NULL),
            ADD CONSTRAINT ck_invoice_version CHECK (version >= 1),
            ADD CONSTRAINT ck_invoice_totals CHECK (
                grand_total >= 0 AND vat_amount >= 0 AND total_net >= 0 AND
                total_before_discount - total_discount = grand_total AND
                total_net + vat_amount = grand_total),
            ADD CONSTRAINT ck_invoice_void_metadata CHECK (
                (posting_status = 'Draft' AND voided_at IS NULL AND voided_by IS NULL AND void_reason_id IS NULL)
                OR (posting_status = 'Voided' AND voided_at IS NOT NULL AND voided_by IS NOT NULL AND void_reason_id IS NOT NULL));
        ALTER TABLE sales.sales_invoice_line
            ALTER COLUMN product_id SET NOT NULL,
            ADD COLUMN line_no integer NOT NULL,
            ADD CONSTRAINT uq_invoice_line_no UNIQUE(invoice_id, line_no),
            ADD CONSTRAINT fk_invoice_line_batch FOREIGN KEY (batch_id, product_id)
                REFERENCES inventory.batch_record(id, product_id),
            ADD CONSTRAINT ck_invoice_line_values CHECK (
                line_no > 0 AND quantity > 0 AND unit_price >= 0 AND
                discount_pct BETWEEN 0 AND 100 AND vat_rate BETWEEN 0 AND 100 AND
                net_price >= 0 AND line_total >= 0 AND vat_amount BETWEEN 0 AND line_total);
        ALTER TABLE master_data.master_product
            ADD CONSTRAINT ck_product_price_vat CHECK (base_price >= 0 AND vat_rate BETWEEN 0 AND 100);
        CREATE INDEX ix_invoice_territory ON sales.sales_invoice(territory_id);
        CREATE INDEX ix_invoice_customer ON sales.sales_invoice(customer_id);
        CREATE INDEX ix_invoice_creator ON sales.sales_invoice(created_by);
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX sales.ix_invoice_creator;
        DROP INDEX sales.ix_invoice_customer;
        DROP INDEX sales.ix_invoice_territory;
        ALTER TABLE master_data.master_product DROP CONSTRAINT ck_product_price_vat;
        ALTER TABLE sales.sales_invoice_line
            DROP CONSTRAINT ck_invoice_line_values,
            DROP CONSTRAINT fk_invoice_line_batch,
            DROP CONSTRAINT uq_invoice_line_no,
            DROP COLUMN line_no,
            ALTER COLUMN product_id DROP NOT NULL;
        ALTER TABLE sales.sales_invoice
            DROP CONSTRAINT ck_invoice_void_metadata,
            DROP CONSTRAINT ck_invoice_totals,
            DROP CONSTRAINT ck_invoice_version,
            DROP CONSTRAINT ck_invoice_posting_disabled,
            DROP CONSTRAINT fk_invoice_warehouse_branch,
            DROP COLUMN voided_by, DROP COLUMN updated_by,
            DROP COLUMN updated_at, DROP COLUMN version, DROP COLUMN territory_id,
            ALTER COLUMN created_by DROP NOT NULL,
            ALTER COLUMN warehouse_id DROP NOT NULL,
            ALTER COLUMN customer_id DROP NOT NULL,
            ALTER COLUMN branch_id DROP NOT NULL;
        DROP TABLE inventory.batch_record;
        DROP TABLE master_data.master_warehouse;
        ALTER TABLE master_data.master_customer DROP COLUMN territory_id;
        DROP TABLE platform.user_territory;
        DROP TABLE master_data.master_territory;
    """)
