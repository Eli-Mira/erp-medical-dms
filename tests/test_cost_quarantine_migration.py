"""Run the actual 1a migration on owned PostgreSQL, including history and locks."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import engine
from app.inventory import service as stock


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location(
        "cost_quarantine_migration", Path("alembic/versions/0021_cost_quarantine.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_flags_preexisting_amount_without_backfill(posting_env, migration):
    _client, db, ids, _auth, _invoice, _payload = posting_env
    with Operations.context(MigrationContext.configure(db.connection())):
        migration.downgrade()
        before = dict(
            db.execute(
                text("""
            INSERT INTO inventory.stock_movement
                (warehouse_id, product_id, movement_type, quantity, unit_cost, created_by)
            VALUES (:w,:p,'opening',1,114.00,:actor) RETURNING *
        """),
                {"w": ids["warehouse"], "p": ids["product"], "actor": ids["owner"]},
            )
            .mappings()
            .one()
        )
        migration.upgrade()
    after = dict(
        db.execute(
            text("SELECT * FROM inventory.stock_movement WHERE id=:id"),
            {"id": before["id"]},
        )
        .mappings()
        .one()
    )
    assert after.pop("cost_status") == "cost_unverified"
    assert after == before


@pytest.mark.parametrize("history", ["movement", "proof", "quarantine"])
def test_downgrade_refuses_to_erase_history(posting_env, migration, history):
    _client, db, ids, _auth, invoice, _payload = posting_env
    if history == "movement":
        stock.record_movement(
            db,
            actor_id=ids["owner"],
            warehouse_id=ids["warehouse"],
            product_id=ids["product"],
            batch_id=None,
            movement_type="opening",
            quantity=1,
            unit_cost=114,
        )
    elif history == "proof":
        db.execute(
            text(
                "UPDATE sales.sales_invoice_line SET verified_unit_cost=60, cost_evidence_ref='SYNTHETIC', cost_verified_by=:actor, cost_verified_at=now() WHERE invoice_id=:id"
            ),
            {"actor": ids["owner"], "id": invoice["id"]},
        )
    else:
        db.execute(
            text(
                "INSERT INTO sales.sales_return(customer_id,product_id,warehouse_id,quantity,return_date,created_by) VALUES (:c,:p,:w,3,CURRENT_DATE,:actor)"
            ),
            {
                "c": ids["customer"],
                "p": ids["product"],
                "w": ids["warehouse"],
                "actor": ids["owner"],
            },
        )
    with (
        Operations.context(MigrationContext.configure(db.connection())),
        pytest.raises(RuntimeError, match="history must be preserved"),
    ):
        migration.downgrade()
    if history == "movement":
        row = (
            db.execute(
                text("SELECT unit_cost, cost_status FROM inventory.stock_movement")
            )
            .mappings()
            .one()
        )
        assert row["unit_cost"] == 114 and row["cost_status"] == "cost_unverified"
    elif history == "proof":
        assert (
            db.execute(
                text(
                    "SELECT verified_unit_cost FROM sales.sales_invoice_line WHERE invoice_id=:id"
                ),
                {"id": invoice["id"]},
            ).scalar_one()
            == 60
        )
    else:
        assert (
            db.execute(text("SELECT status FROM sales.sales_return")).scalar_one()
            == "quarantined"
        )


def test_downgrade_blocks_racing_writes_before_check_and_ddl(
    posting_env, migration, monkeypatch
):
    _client, db, _ids, _auth, invoice, _payload = posting_env
    connection = db.connection()
    observed = []

    class CheckedBind:
        def execute(self, statement):
            result = connection.execute(statement)
            if str(statement).lstrip().startswith("SELECT EXISTS"):
                with pytest.raises(OperationalError) as caught, engine.begin() as other:
                    other.execute(text("SET LOCAL lock_timeout='100ms'"))
                    other.execute(
                        text(
                            "UPDATE sales.sales_invoice_line SET notes=notes WHERE invoice_id=:id"
                        ),
                        {"id": invoice["id"]},
                    )
                assert caught.value.orig.sqlstate == "55P03"
                observed.append(caught.value.orig.sqlstate)
            return result

    transaction = connection.begin_nested()
    try:
        with Operations.context(MigrationContext.configure(connection)):
            monkeypatch.setattr(migration.op, "get_bind", lambda: CheckedBind())
            migration.downgrade()
    finally:
        transaction.rollback()
    assert observed == ["55P03"]
