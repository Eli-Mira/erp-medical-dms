"""Real-PostgreSQL invoice persistence constraints (not SQLite approximations)."""
from sqlalchemy import inspect

from app.db import engine


def test_invoice_reference_and_safety_schema_exists():
    inspector = inspect(engine)
    master = set(inspector.get_table_names(schema="master_data"))
    assert {"master_territory", "master_warehouse"} <= master
    assert "user_territory" in inspector.get_table_names(schema="platform")
    assert "batch_record" in inspector.get_table_names(schema="inventory")
    columns = {c["name"] for c in inspector.get_columns("sales_invoice", schema="sales")}
    assert {"territory_id", "version", "updated_at", "updated_by", "voided_by", "posted_by"} <= columns
    checks = {c["name"] for c in inspector.get_check_constraints("sales_invoice", schema="sales")}
    # posting gate: status must be a known state, and a Posted row must carry posted_at
    assert {"ck_invoice_posting_status", "ck_invoice_posted_at"} <= checks
