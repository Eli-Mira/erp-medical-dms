"""Invoice collections: payment receipts, reversal support, and related constraints.

- finance.payment_receipt: invoice-linked receipts (one invoice per receipt,
  partial receipts allowed). Exact positive two-decimal amount, receipt number,
  date, cash/check/transfer method, optional note. Derives customer/branch from
  locked Posted invoice. Server-owned status/actor/totals. Unique receipt number
  per branch.
- Appends exact stock + AR counter-entries on reversal/void.
- Constraints for idempotency, overpayment rejection, terminal-row immutability.
"""

from alembic import op

revision = "0010_invoice_collections"
down_revision = "0009_sales_source_warehouse"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS finance;

        CREATE TABLE finance.payment_receipt (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            invoice_id uuid NOT NULL REFERENCES sales.sales_invoice(id),
            branch_id uuid NOT NULL REFERENCES master_data.master_branch(id),
            customer_id uuid NOT NULL REFERENCES master_data.master_customer(id),
            receipt_no varchar(30) NOT NULL,
            receipt_date date NOT NULL,
            amount numeric(14,2) NOT NULL,
            method varchar(20) NOT NULL,
            note text,
            status varchar(20) NOT NULL DEFAULT 'Active',
            voided_at timestamptz,
            voided_by uuid REFERENCES platform.platform_user(id),
            void_reason_id uuid REFERENCES audit.reason_code(id),
            created_by uuid NOT NULL REFERENCES platform.platform_user(id),
            updated_by uuid REFERENCES platform.platform_user(id),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            version integer NOT NULL DEFAULT 1,
            CONSTRAINT ck_receipt_amount_positive CHECK (amount > 0),
            CONSTRAINT ck_receipt_method CHECK (method IN ('cash', 'check', 'transfer')),
            CONSTRAINT ck_receipt_status CHECK (status IN ('Active', 'Voided')),
            CONSTRAINT ck_receipt_void_metadata CHECK (
                (status = 'Active' AND voided_at IS NULL AND voided_by IS NULL AND void_reason_id IS NULL)
                OR (status = 'Voided' AND voided_at IS NOT NULL AND voided_by IS NOT NULL AND void_reason_id IS NOT NULL)),
            CONSTRAINT ck_receipt_version CHECK (version >= 1)
        );

        CREATE UNIQUE INDEX uq_receipt_branch_no ON finance.payment_receipt(branch_id, receipt_no);
        CREATE INDEX ix_receipt_invoice ON finance.payment_receipt(invoice_id);
        CREATE INDEX ix_receipt_customer ON finance.payment_receipt(customer_id);
        CREATE INDEX ix_receipt_branch ON finance.payment_receipt(branch_id);
        ALTER TABLE sales.sales_invoice
            ADD CONSTRAINT uq_invoice_receipt_scope UNIQUE(id, branch_id, customer_id),
            ADD CONSTRAINT ck_invoice_posting_actor CHECK (
                (posted_at IS NULL) = (posted_by IS NULL)
                AND (posting_status != 'Draft' OR posted_at IS NULL));
        ALTER TABLE finance.payment_receipt
            ADD CONSTRAINT fk_receipt_invoice_scope FOREIGN KEY(invoice_id, branch_id, customer_id)
                REFERENCES sales.sales_invoice(id, branch_id, customer_id),
            ADD CONSTRAINT ck_receipt_no CHECK (length(btrim(receipt_no)) > 0),
            ADD CONSTRAINT ck_receipt_finite CHECK (amount < 'Infinity'::numeric);
        ALTER TABLE finance.ar_entry
            ADD COLUMN receipt_id uuid REFERENCES finance.payment_receipt(id),
            ADD COLUMN reverses_entry_id uuid UNIQUE REFERENCES finance.ar_entry(id);
        CREATE UNIQUE INDEX uq_ar_invoice_sale ON finance.ar_entry(invoice_id) WHERE entry_type='invoice';
        CREATE UNIQUE INDEX uq_ar_receipt_type ON finance.ar_entry(receipt_id,entry_type) WHERE receipt_id IS NOT NULL;
        ALTER TABLE inventory.stock_movement
            ADD COLUMN invoice_line_id uuid REFERENCES sales.sales_invoice_line(id),
            ADD COLUMN reverses_movement_id uuid UNIQUE REFERENCES inventory.stock_movement(id);
        CREATE UNIQUE INDEX uq_stock_invoice_line_sale ON inventory.stock_movement(invoice_line_id)
            WHERE movement_type='sale' AND invoice_line_id IS NOT NULL;

        CREATE FUNCTION sales.guard_terminal_invoice() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.posting_status != 'Draft' THEN
                IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Terminal invoice history is immutable'; END IF;
                IF NOT (OLD.posting_status='Posted' AND NEW.posting_status='Voided'
                    AND NEW.version=OLD.version+1
                    AND (to_jsonb(NEW)-ARRAY['posting_status','version','voided_at','voided_by','void_reason_id','updated_at','updated_by'])
                      = (to_jsonb(OLD)-ARRAY['posting_status','version','voided_at','voided_by','void_reason_id','updated_at','updated_by'])) THEN
                    RAISE EXCEPTION 'Terminal invoice history is immutable';
                END IF;
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER guard_terminal_invoice BEFORE UPDATE OR DELETE ON sales.sales_invoice
            FOR EACH ROW EXECUTE FUNCTION sales.guard_terminal_invoice();
        CREATE FUNCTION sales.guard_terminal_line() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE target uuid; status text;
        BEGIN
            IF TG_OP='INSERT' THEN target:=NEW.invoice_id; ELSE target:=OLD.invoice_id; END IF;
            SELECT posting_status INTO status FROM sales.sales_invoice WHERE id=target FOR UPDATE;
            IF status IS DISTINCT FROM 'Draft' THEN RAISE EXCEPTION 'Terminal invoice lines are immutable'; END IF;
            IF TG_OP='UPDATE' AND NEW.invoice_id != OLD.invoice_id THEN RAISE EXCEPTION 'Invoice lines cannot be reparented'; END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER guard_terminal_line BEFORE INSERT OR UPDATE OR DELETE ON sales.sales_invoice_line
            FOR EACH ROW EXECUTE FUNCTION sales.guard_terminal_line();
        CREATE FUNCTION finance.guard_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Financial and stock ledgers are append-only'; END $$;
        CREATE TRIGGER guard_ar_history BEFORE UPDATE OR DELETE ON finance.ar_entry
            FOR EACH ROW EXECUTE FUNCTION finance.guard_append_only();
        CREATE TRIGGER guard_stock_history BEFORE UPDATE OR DELETE ON inventory.stock_movement
            FOR EACH ROW EXECUTE FUNCTION finance.guard_append_only();
        CREATE FUNCTION finance.guard_receipt_history() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Receipt history is immutable'; END IF;
            IF NOT (OLD.status='Active' AND NEW.status='Voided' AND NEW.version=OLD.version+1
                AND (to_jsonb(NEW)-ARRAY['status','version','voided_at','voided_by','void_reason_id','updated_at','updated_by'])
                  = (to_jsonb(OLD)-ARRAY['status','version','voided_at','voided_by','void_reason_id','updated_at','updated_by'])) THEN
                RAISE EXCEPTION 'Receipt history is immutable';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER guard_receipt_history BEFORE UPDATE OR DELETE ON finance.payment_receipt
            FOR EACH ROW EXECUTE FUNCTION finance.guard_receipt_history();
        """
    )


def downgrade() -> None:
    from sqlalchemy import text

    used = (
        op.get_bind()
        .execute(
            text("""
        SELECT EXISTS(SELECT 1 FROM finance.payment_receipt)
            OR EXISTS(SELECT 1 FROM finance.ar_entry WHERE receipt_id IS NOT NULL OR reverses_entry_id IS NOT NULL)
            OR EXISTS(SELECT 1 FROM inventory.stock_movement WHERE invoice_line_id IS NOT NULL OR reverses_movement_id IS NOT NULL)
    """)
        )
        .scalar_one()
    )
    if used:
        raise RuntimeError(
            "Cannot downgrade: invoice/collection history must be preserved"
        )
    op.execute("""
        DROP TRIGGER guard_receipt_history ON finance.payment_receipt;
        DROP FUNCTION finance.guard_receipt_history();
        DROP TRIGGER guard_stock_history ON inventory.stock_movement;
        DROP TRIGGER guard_ar_history ON finance.ar_entry;
        DROP FUNCTION finance.guard_append_only();
        DROP TRIGGER guard_terminal_line ON sales.sales_invoice_line;
        DROP FUNCTION sales.guard_terminal_line();
        DROP TRIGGER guard_terminal_invoice ON sales.sales_invoice;
        DROP FUNCTION sales.guard_terminal_invoice();
        DROP INDEX inventory.uq_stock_invoice_line_sale;
        ALTER TABLE inventory.stock_movement DROP COLUMN reverses_movement_id, DROP COLUMN invoice_line_id;
        DROP INDEX finance.uq_ar_receipt_type;
        DROP INDEX finance.uq_ar_invoice_sale;
        ALTER TABLE finance.ar_entry DROP COLUMN reverses_entry_id, DROP COLUMN receipt_id;
        DROP TABLE finance.payment_receipt;
        ALTER TABLE sales.sales_invoice DROP CONSTRAINT uq_invoice_receipt_scope, DROP CONSTRAINT ck_invoice_posting_actor;
    """)
