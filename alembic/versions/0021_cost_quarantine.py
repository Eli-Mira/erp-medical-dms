"""Verified issue-cost snapshots and quarantine-first return intake.

Legacy monetary values remain untouched and explicitly cost_unverified.
"""

from sqlalchemy import text

from alembic import op

revision = "0021_cost_quarantine"
down_revision = "0020_stock_visit_invariants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE sales.sales_invoice_line
            ADD COLUMN verified_unit_cost numeric(12,2),
            ADD COLUMN cost_evidence_ref text,
            ADD COLUMN cost_verified_by uuid REFERENCES platform.platform_user(id),
            ADD COLUMN cost_verified_at timestamptz,
            ADD CONSTRAINT ck_invoice_line_cost_proof CHECK (
                (verified_unit_cost IS NULL AND cost_evidence_ref IS NULL
                 AND cost_verified_by IS NULL AND cost_verified_at IS NULL)
                OR
                (verified_unit_cost IS NOT NULL AND verified_unit_cost >= 0
                 AND verified_unit_cost <> 'NaN'::numeric
                 AND cost_evidence_ref IS NOT NULL
                 AND length(btrim(cost_evidence_ref)) BETWEEN 1 AND 240
                 AND cost_verified_by IS NOT NULL AND cost_verified_at IS NOT NULL)
            );
        ALTER TABLE inventory.stock_movement
            ADD COLUMN cost_status varchar(20) NOT NULL DEFAULT 'cost_unverified',
            ADD CONSTRAINT ck_stock_cost_status
                CHECK (cost_status IN ('cost_unverified', 'cost_verified'));
        CREATE FUNCTION inventory.guard_verified_cost() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.cost_status = 'cost_verified' AND NOT EXISTS (
                SELECT 1 FROM sales.sales_invoice_line l
                JOIN sales.sales_invoice h ON h.id = l.invoice_id
                WHERE l.id = NEW.invoice_line_id
                  AND l.verified_unit_cost = NEW.unit_cost
                  AND l.cost_verified_by IS NOT NULL AND l.cost_verified_at IS NOT NULL
                  AND l.cost_evidence_ref IS NOT NULL
                  AND NEW.source_type = 'invoice' AND NEW.source_id = h.id
                  AND NEW.product_id = l.product_id
                  AND NEW.batch_id IS NOT DISTINCT FROM l.batch_id
                  AND NEW.warehouse_id = h.warehouse_id
            ) THEN
                RAISE EXCEPTION 'Verified movement cost requires matching invoice-line proof'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER guard_verified_cost BEFORE INSERT ON inventory.stock_movement
            FOR EACH ROW EXECUTE FUNCTION inventory.guard_verified_cost();
        ALTER TABLE sales.sales_return
            DROP CONSTRAINT sales_return_status_check,
            ADD CONSTRAINT sales_return_status_check
                CHECK (status IN ('recorded', 'approved', 'rejected', 'quarantined')),
            ALTER COLUMN status SET DEFAULT 'quarantined';
    """)


def downgrade() -> None:
    # Keep the check and DDL indivisible; never erase provenance or quarantine history.
    op.execute("""
        LOCK TABLE sales.sales_invoice, sales.sales_invoice_line,
            inventory.stock_movement, sales.sales_return IN ACCESS EXCLUSIVE MODE
    """)
    used = (
        op.get_bind()
        .execute(
            text("""
        SELECT EXISTS(SELECT 1 FROM inventory.stock_movement)
            OR EXISTS(SELECT 1 FROM sales.sales_return)
            OR EXISTS(SELECT 1 FROM sales.sales_invoice_line WHERE verified_unit_cost IS NOT NULL)
    """)
        )
        .scalar_one()
    )
    if used:
        raise RuntimeError(
            "Cannot downgrade: cost and quarantine history must be preserved"
        )
    op.execute("""
        ALTER TABLE sales.sales_return
            DROP CONSTRAINT sales_return_status_check,
            ADD CONSTRAINT sales_return_status_check
                CHECK (status IN ('recorded', 'approved', 'rejected')),
            ALTER COLUMN status SET DEFAULT 'recorded';
        DROP TRIGGER guard_verified_cost ON inventory.stock_movement;
        DROP FUNCTION inventory.guard_verified_cost();
        ALTER TABLE inventory.stock_movement
            DROP CONSTRAINT ck_stock_cost_status,
            DROP COLUMN cost_status;
        ALTER TABLE sales.sales_invoice_line
            DROP CONSTRAINT ck_invoice_line_cost_proof,
            DROP COLUMN verified_unit_cost,
            DROP COLUMN cost_evidence_ref,
            DROP COLUMN cost_verified_by,
            DROP COLUMN cost_verified_at;
    """)
