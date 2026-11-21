import pytest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import text
from test_invoice_cycle_controls import scalar, sql

from app.db import SessionLocal
from app.inventory import service as inv_service
from app.transfers import router as transfer_router

pytest_plugins = ["test_invoice_cycle_controls"]

def test_lock_balance_rows_orders_canonically():
    w_lo = "00000000-0000-0000-0000-000000000001"
    w_hi = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    prod = uuid4()
    calls = []
    class FakeDB:
        def execute(self, stmt, params=None):
            calls.append((str(stmt), params))
            return SimpleNamespace(scalar_one_or_none=lambda: None)
    fake_db = FakeDB()
    inv_service.lock_balance_rows(fake_db, [(w_hi, prod, None, False), (w_lo, prod, None, True)])
    for_update = [c for c in calls if "FOR UPDATE" in c[0]]
    assert len(for_update) == 2
    assert for_update[0][1]["w"] == w_lo
    assert for_update[1][1]["w"] == w_hi

def test_concurrent_bidirectional_unbatched_and_batched_transfers(life):
    owner = sql("SELECT id, username, role, is_owner, is_active FROM platform.platform_user WHERE role='owner' AND is_owner LIMIT 1")[0]
    prod = life.ids["product"]
    wh_a, wh_b = life.ids["warehouse"], life.ids["other_warehouse"]
    sql("INSERT INTO inventory.stock_balance (warehouse_id, product_id, batch_id, quantity) VALUES (:a, :p, NULL, 500), (:b, :p, NULL, 500) ON CONFLICT (warehouse_id, product_id) WHERE batch_id IS NULL DO UPDATE SET quantity = 500", a=wh_a, b=wh_b, p=prod)
    batch_a, batch_b = uuid4(), uuid4()
    batch_no = f"RC2-{uuid4().hex[:8]}"
    expiry = scalar("SELECT CURRENT_DATE") + timedelta(days=365)
    sql("INSERT INTO inventory.batch_record (id, batch_no, product_id, warehouse_id, manufacture_date, expiry_date) VALUES (:a, :n, :p, :wa, :m, :e), (:b, :n, :p, :wb, :m, :e)", a=batch_a, b=batch_b, n=batch_no, p=prod, wa=wh_a, wb=wh_b, m=date(2026,1,1), e=expiry)
    sql("INSERT INTO inventory.stock_balance (warehouse_id, product_id, batch_id, quantity) VALUES (:a, :p, :ba, 500), (:b, :p, :bb, 500)", a=wh_a, b=wh_b, ba=batch_a, bb=batch_b, p=prod)
    def run_one(src, dst, batch_id):
        db = SessionLocal()
        try:
            transfer_router.create_transfer({"source_warehouse_id": str(src), "destination_warehouse_id": str(dst), "product_id": str(prod), "batch_id": str(batch_id) if batch_id else None, "quantity": "1"}, SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={"user-agent": "rc2-02"}), db, owner)
        finally:
            db.close()
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = []
        for i in range(30):
            futures.append(ex.submit(run_one, wh_a, wh_b, None))
            futures.append(ex.submit(run_one, wh_b, wh_a, None))
        for f in futures:
            f.result()
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = []
        for i in range(30):
            futures.append(ex.submit(run_one, wh_a, wh_b, batch_a))
            futures.append(ex.submit(run_one, wh_b, wh_a, batch_b))
        for f in futures:
            f.result()
    assert scalar("SELECT SUM(quantity) FROM inventory.stock_balance WHERE product_id=:p AND batch_id IS NULL", p=prod) == Decimal("1000")
    assert scalar("SELECT SUM(quantity) FROM inventory.stock_balance WHERE product_id=:p AND batch_id IN (:a, :b)", p=prod, a=batch_a, b=batch_b) == Decimal("1000")
    assert scalar("SELECT COUNT(*) FROM inventory.stock_movement WHERE source_type='transfer' AND product_id=:p", p=prod) == 240
