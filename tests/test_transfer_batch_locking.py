"""Real competing writer proves reused destination metadata stays locked."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_invoice_cycle_controls import scalar, sql

from app.db import engine
from app.transfers import router as transfer_router

pytest_plugins = ["test_invoice_cycle_controls"]


@pytest.mark.parametrize("manufacture_date", [None, date(2026, 1, 1)])
def test_transfer_locks_reused_destination_batch_until_commit(
    life, monkeypatch, manufacture_date
):
    source, destination = uuid4(), uuid4()
    expiry = scalar("SELECT CURRENT_DATE") + timedelta(days=365)
    batch_no = uuid4().hex
    for batch, warehouse in (
        (source, life.ids["warehouse"]),
        (destination, life.ids["other_warehouse"]),
    ):
        sql(
            "INSERT INTO inventory.batch_record "
            "(id,product_id,warehouse_id,batch_no,manufacture_date,expiry_date) "
            "VALUES (:b,:p,:w,:n,:m,:e)",
            b=batch,
            p=life.ids["product"],
            w=warehouse,
            n=batch_no,
            m=manufacture_date,
            e=expiry,
        )
    sql(
        "INSERT INTO inventory.stock_balance "
        "(warehouse_id,product_id,batch_id,quantity) VALUES (:w,:p,:b,10)",
        w=life.ids["warehouse"],
        p=life.ids["product"],
        b=source,
    )
    original = transfer_router.inv_service.record_movement
    probes = []

    def probe_before_movement(db, **kwargs):
        if kwargs["movement_type"] == "transfer_out":
            transfer_pid = db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            # Probe the real row while the transfer is between validation and commit.
            with engine.connect() as writer, writer.begin():
                writer.exec_driver_sql("SET LOCAL lock_timeout='150ms'")
                writer.exec_driver_sql("SET LOCAL statement_timeout='2s'")
                writer_pid = writer.exec_driver_sql(
                    "SELECT pg_backend_pid()"
                ).scalar_one()
                assert writer_pid != transfer_pid
                with pytest.raises(DBAPIError) as blocked:
                    writer.execute(
                        text(
                            "UPDATE inventory.batch_record SET expiry_date=expiry_date+1 "
                            "WHERE id=:id"
                        ),
                        {"id": destination},
                    )
                assert blocked.value.orig.sqlstate == "55P03"
                probes.append((transfer_pid, writer_pid))
                writer.rollback()
        return original(db, **kwargs)

    monkeypatch.setattr(
        transfer_router.inv_service, "record_movement", probe_before_movement
    )
    response = life.client.post(
        "/transfers",
        headers=life.auth["owner"],
        json={
            "source_warehouse_id": str(life.ids["warehouse"]),
            "destination_warehouse_id": str(life.ids["other_warehouse"]),
            "product_id": str(life.ids["product"]),
            "batch_id": str(source),
            "quantity": "4",
        },
    )
    assert response.status_code == 201, response.text
    assert len(probes) == 1
    assert sql(
        "SELECT manufacture_date,expiry_date FROM inventory.batch_record WHERE id=:id",
        id=destination,
    ) == [{"manufacture_date": manufacture_date, "expiry_date": expiry}]
    assert (
        scalar(
            "SELECT quantity FROM inventory.stock_balance WHERE batch_id=:b", b=source
        )
        == 6
    )
    assert (
        scalar(
            "SELECT quantity FROM inventory.stock_balance WHERE batch_id=:b",
            b=destination,
        )
        == 4
    )
    assert (
        scalar(
            "SELECT count(*) FROM inventory.stock_movement WHERE source_type='transfer'"
        )
        == 2
    )
    assert (
        scalar(
            "SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_transfer'"
        )
        == 1
    )
    for table in ("sales.sales_invoice", "finance.ar_entry", "finance.payment_receipt"):
        assert scalar(f"SELECT count(*) FROM {table}") == 0
    # The lock must end at commit: the same harmless writer now succeeds, then rolls back.
    with engine.connect() as writer, writer.begin():
        writer.exec_driver_sql("SET LOCAL lock_timeout='150ms'")
        result = writer.execute(
            text(
                "UPDATE inventory.batch_record SET expiry_date=expiry_date+1 WHERE id=:id"
            ),
            {"id": destination},
        )
        assert result.rowcount == 1
        writer.rollback()
    assert (
        scalar(
            "SELECT expiry_date FROM inventory.batch_record WHERE id=:id",
            id=destination,
        )
        == expiry
    )
