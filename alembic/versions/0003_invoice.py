"""Invoice module schema (Vertical Slice 1).

Matches DATABASE_SCHEMA.md:
  - master_data.master_branch / master_product / master_customer (minimal
    references the invoice needs; full Master Data module comes later).
  - sales.sales_invoice (header) + sales_invoice_line (lines).
  - batch_id / warehouse_id / rep_id columns are present but their FKs are
    deferred to the Inventory / Master Data modules (D-scope cut).

Money = Numeric (exact decimal). Net price E = C × (1 − D) (D18). VAT-inclusive
(D36): total_net is ex-VAT, grand_total is incl-VAT, vat_amount is the VAT.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_invoice"
down_revision = "0002_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS master_data")
    op.execute("CREATE SCHEMA IF NOT EXISTS sales")

    op.create_table(
        "master_branch",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="master_data",
    )

    op.create_table(
        "master_product",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("sku", sa.String(50), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200)),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False,
                  server_default=sa.text("14.00")),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="master_data",
    )

    op.create_table(
        "master_customer",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(30), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200)),
        sa.Column("branch_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("master_data.master_branch.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        schema="master_data",
    )

    op.create_table(
        "sales_invoice",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("invoice_no", sa.String(30), nullable=False),
        sa.Column("branch_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("master_data.master_branch.id")),
        sa.Column("warehouse_id", sa.UUID(as_uuid=True)),  # FK deferred
        sa.Column("customer_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("master_data.master_customer.id")),
        sa.Column("rep_id", sa.UUID(as_uuid=True)),         # FK deferred
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("posting_status", sa.String(20), nullable=False,
                  server_default="Draft"),
        sa.Column("total_before_discount", sa.Numeric(14, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("total_discount", sa.Numeric(14, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("total_net", sa.Numeric(14, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("grand_total", sa.Numeric(14, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.UUID(as_uuid=True),
                  sa.ForeignKey("platform.platform_user.id")),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("audit.reason_code.id")),
        sa.UniqueConstraint("branch_id", "invoice_no",
                             name="uq_sales_invoice_branch_no"),
        schema="sales",
    )

    op.create_table(
        "sales_invoice_line",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("invoice_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("sales.sales_invoice.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("product_id", sa.UUID(as_uuid=True),
                  sa.ForeignKey("master_data.master_product.id")),
        sa.Column("batch_id", sa.UUID(as_uuid=True)),       # FK deferred
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("net_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        schema="sales",
    )


def downgrade() -> None:
    op.drop_table("sales_invoice_line", schema="sales")
    op.drop_table("sales_invoice", schema="sales")
    op.drop_table("master_customer", schema="master_data")
    op.drop_table("master_product", schema="master_data")
    op.drop_table("master_branch", schema="master_data")
    op.execute("DROP SCHEMA IF EXISTS sales")
    op.execute("DROP SCHEMA IF EXISTS master_data")
