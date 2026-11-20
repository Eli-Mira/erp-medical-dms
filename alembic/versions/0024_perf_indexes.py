"""Non-destructive performance indexes (P8 / Phase 3)."""

from alembic import op

revision = "0024_perf_indexes"
down_revision = "0023_audit_append_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sales_invoice_date_created "
            "ON sales.sales_invoice (invoice_date DESC, created_at DESC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sales_invoice_customer_date "
            "ON sales.sales_invoice (customer_id, invoice_date DESC, created_at DESC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sales_invoice_status_date "
            "ON sales.sales_invoice (posting_status, invoice_date DESC, created_at DESC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sales_invoice_posted_date_cover "
            "ON sales.sales_invoice (invoice_date DESC, created_at DESC) "
            "INCLUDE (id, posted_at, warehouse_id, territory_id, created_by, "
            "total_before_discount, total_discount, total_net, vat_amount, grand_total) "
            "WHERE posting_status = 'Posted';"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_sales_invoice_line_invoice_cover "
            "ON sales.sales_invoice_line (invoice_id) "
            "INCLUDE (product_id, quantity, line_total, vat_amount);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ar_entry_customer_date_cover "
            "ON finance.ar_entry (customer_id, entry_date ASC, id ASC) "
            "INCLUDE (debit, credit);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_ar_entry_date_id "
            "ON finance.ar_entry (entry_date DESC, id ASC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payment_receipt_date_id "
            "ON finance.payment_receipt (receipt_date DESC, id ASC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payment_receipt_active_date_cover "
            "ON finance.payment_receipt (receipt_date DESC) "
            "INCLUDE (amount, customer_id) "
            "WHERE status = 'Active';"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payment_receipt_invoice_active_cover "
            "ON finance.payment_receipt (invoice_id) "
            "INCLUDE (amount) "
            "WHERE status = 'Active';"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_stock_movement_created_id "
            "ON inventory.stock_movement (created_at DESC, id ASC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_stock_movement_source "
            "ON inventory.stock_movement (source_type, source_id) "
            "WHERE source_id IS NOT NULL;"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_batch_record_expiry_no "
            "ON inventory.batch_record (expiry_date ASC, batch_no ASC, id ASC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_audit_log_created_at_desc "
            "ON audit.audit_log (created_at DESC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_audit_log_entity_action_created "
            "ON audit.audit_log (entity_type, action, created_at DESC);"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_audit_log_actor_created "
            "ON audit.audit_log (actor_user_id, created_at DESC) "
            "WHERE actor_user_id IS NOT NULL;"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_master_customer_trgm_code "
            "ON master_data.master_customer USING gin (code gin_trgm_ops) "
            "WHERE is_active AND territory_id IS NOT NULL AND branch_id IS NOT NULL;"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_master_customer_trgm_name_ar "
            "ON master_data.master_customer USING gin (name_ar gin_trgm_ops) "
            "WHERE is_active AND territory_id IS NOT NULL AND branch_id IS NOT NULL;"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_master_customer_trgm_name_en "
            "ON master_data.master_customer USING gin (name_en gin_trgm_ops) "
            "WHERE is_active AND territory_id IS NOT NULL AND branch_id IS NOT NULL;"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_master_product_trgm_sku "
            "ON master_data.master_product USING gin (sku gin_trgm_ops) "
            "WHERE is_active;"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_master_product_trgm_name_ar "
            "ON master_data.master_product USING gin (name_ar gin_trgm_ops) "
            "WHERE is_active;"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_master_product_trgm_name_en "
            "ON master_data.master_product USING gin (name_en gin_trgm_ops) "
            "WHERE is_active;"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS master_data.ix_master_product_trgm_name_en;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS master_data.ix_master_product_trgm_name_ar;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS master_data.ix_master_product_trgm_sku;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS master_data.ix_master_customer_trgm_name_en;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS master_data.ix_master_customer_trgm_name_ar;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS master_data.ix_master_customer_trgm_code;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS audit.ix_audit_log_actor_created;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS audit.ix_audit_log_entity_action_created;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS audit.ix_audit_log_created_at_desc;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS inventory.ix_batch_record_expiry_no;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS inventory.ix_stock_movement_source;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS inventory.ix_stock_movement_created_id;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS finance.ix_payment_receipt_invoice_active_cover;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS finance.ix_payment_receipt_active_date_cover;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS finance.ix_payment_receipt_date_id;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS finance.ix_ar_entry_date_id;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS finance.ix_ar_entry_customer_date_cover;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS sales.ix_sales_invoice_line_invoice_cover;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS sales.ix_sales_invoice_posted_date_cover;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS sales.ix_sales_invoice_status_date;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS sales.ix_sales_invoice_customer_date;")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS sales.ix_sales_invoice_date_created;")
