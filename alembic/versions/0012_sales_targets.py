"""Sales-target model: per-rep monthly targets in units (V2 §2B.13).

Owner decision 2026-10-19: one row = required rep + optional product +
month (normalized to first-of-day-of-month) + target quantity. Territory
and value roll-ups stay computable from rep assignments and posted-invoice
lines — never duplicated per territory. A NULL product means the rep's
whole book, so the uniqueness care splits into two partial unique indexes
(NULL is never deduplicated by a plain UNIQUE constraint).
"""
from alembic import op

revision = "0012_sales_targets"
down_revision = "0011_master_data_b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sales.sales_target (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            rep_id uuid NOT NULL REFERENCES platform.platform_user(id),
            product_id uuid REFERENCES master_data.master_product(id),
            period_month date NOT NULL,
            target_quantity numeric(12,3) NOT NULL CHECK (target_quantity >= 0),
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (period_month = date_trunc('month', period_month)::date)
        );
        CREATE UNIQUE INDEX uq_target_rep_book_month
            ON sales.sales_target(rep_id, period_month) WHERE product_id IS NULL;
        CREATE UNIQUE INDEX uq_target_rep_product_month
            ON sales.sales_target(rep_id, product_id, period_month)
            WHERE product_id IS NOT NULL;
        CREATE INDEX ix_sales_target_rep_month ON sales.sales_target(rep_id, period_month);
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE sales.sales_target;
    """)
