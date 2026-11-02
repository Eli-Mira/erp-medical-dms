"""Add explicit territory target scope without replacing representative targets."""

from sqlalchemy import text

from alembic import op

revision = "0022_territory_targets"
down_revision = "0021_cost_quarantine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales.sales_target
            ADD COLUMN territory_id uuid REFERENCES master_data.master_territory(id),
            ALTER COLUMN rep_id DROP NOT NULL,
            ADD CONSTRAINT ck_target_one_scope
                CHECK (num_nonnulls(rep_id, territory_id) = 1);
        CREATE UNIQUE INDEX uq_target_territory_book_month
            ON sales.sales_target(territory_id, period_month)
            WHERE product_id IS NULL AND territory_id IS NOT NULL;
        CREATE UNIQUE INDEX uq_target_territory_product_month
            ON sales.sales_target(territory_id, product_id, period_month)
            WHERE product_id IS NOT NULL AND territory_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("LOCK TABLE sales.sales_target IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM sales.sales_target WHERE territory_id IS NOT NULL)"
        )
    ):
        raise RuntimeError("Cannot downgrade: territory targets must be preserved")
    op.execute("""
        DROP INDEX sales.uq_target_territory_product_month;
        DROP INDEX sales.uq_target_territory_book_month;
        ALTER TABLE sales.sales_target
            DROP CONSTRAINT ck_target_one_scope,
            ALTER COLUMN rep_id SET NOT NULL,
            DROP COLUMN territory_id;
    """)
