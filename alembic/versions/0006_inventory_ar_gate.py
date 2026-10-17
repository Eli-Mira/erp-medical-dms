"""Minimal territory/warehouse mapping + posting-status gates (AR/Inventory slice).

- platform.user_branch: the minimum explicit user->branch assignment. Branches
  own warehouses (master_warehouse.branch_id), so a branch assignment scopes
  access to that branch's warehouses. This is NOT a new dependency on ERPNext
  and does not merge territory and warehouse: territories (user_territory) stay
  territory-scoped for customers, while branches scope warehouses. Some
  territories share warehouses naturally because multiple branches can serve
  overlapping territories via their customers.
- Posting gate change: ck_invoice_posting_disabled (which forbade 'Posted'
  entirely) is replaced by two checks that still forbid a Posted row without
  a posted_at, and forbid posting_status='Posted' unless posted_at is set.
  Real posting lives only behind post_invoice_atomic; the HTTP endpoint
  remains disabled (409) until that transaction is tested and approved.
- Adds posted_by to sales_invoice (audit: who posted).
"""
from alembic import op

revision = "0006_inventory_ar_gate"
down_revision = "0005_inventory_stock"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE platform.user_branch (
            user_id uuid NOT NULL REFERENCES platform.platform_user(id) ON DELETE CASCADE,
            branch_id uuid NOT NULL REFERENCES master_data.master_branch(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, branch_id)
        );

        ALTER TABLE sales.sales_invoice DROP CONSTRAINT ck_invoice_posting_disabled;
        ALTER TABLE sales.sales_invoice ADD COLUMN posted_by uuid REFERENCES platform.platform_user(id);
        ALTER TABLE sales.sales_invoice ADD CONSTRAINT ck_invoice_posting_status
            CHECK (posting_status IN ('Draft', 'Voided', 'Posted'));
        ALTER TABLE sales.sales_invoice ADD CONSTRAINT ck_invoice_posted_at
            CHECK (posted_at IS NOT NULL OR posting_status != 'Posted');
        ALTER TABLE sales.sales_invoice DROP CONSTRAINT ck_invoice_void_metadata;
        ALTER TABLE sales.sales_invoice ADD CONSTRAINT ck_invoice_void_metadata CHECK (
            (posting_status = 'Draft' AND voided_at IS NULL AND voided_by IS NULL AND void_reason_id IS NULL)
            OR (posting_status = 'Voided' AND voided_at IS NOT NULL AND voided_by IS NOT NULL AND void_reason_id IS NOT NULL)
            OR (posting_status = 'Posted' AND voided_at IS NULL AND voided_by IS NULL AND void_reason_id IS NULL));
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE sales.sales_invoice DROP CONSTRAINT ck_invoice_void_metadata;
        ALTER TABLE sales.sales_invoice ADD CONSTRAINT ck_invoice_void_metadata CHECK (
            (posting_status = 'Draft' AND voided_at IS NULL AND voided_by IS NULL AND void_reason_id IS NULL)
            OR (posting_status = 'Voided' AND voided_at IS NOT NULL AND voided_by IS NOT NULL AND void_reason_id IS NOT NULL));
        ALTER TABLE sales.sales_invoice
            DROP CONSTRAINT ck_invoice_posted_at,
            DROP CONSTRAINT ck_invoice_posting_status,
            ADD CONSTRAINT ck_invoice_posting_disabled
                CHECK (posting_status IN ('Draft', 'Voided') AND posted_at IS NULL);
        ALTER TABLE sales.sales_invoice DROP COLUMN posted_by;
        DROP TABLE platform.user_branch;
    """)
