"""Independent-session durability and competing S7 HTTP writes on disposable PG."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import engine, get_db
from app.main import app


def test_s7_durable_competing_visits_and_delete_projection():
    assert os.environ.get("APP_ENV") == "test"
    assert engine.url.database.startswith("dms_cycle_test_")
    assert get_db not in app.dependency_overrides
    ids = {
        key: uuid4()
        for key in ("owner", "session", "customer", "territory", "branch", "product")
    }
    with engine.begin() as db:
        assert (
            db.execute(text("SELECT current_database()")).scalar_one()
            == engine.url.database
        )
        db.execute(
            text(
                "INSERT INTO platform.platform_user(id,username,password_hash,role,is_owner) VALUES (:id,:name,'unused','owner',true)"
            ),
            {"id": ids["owner"], "name": "s7_durable_" + ids["owner"].hex},
        )
        db.execute(
            text(
                "INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:id,:owner,now()+interval '1 hour')"
            ),
            {"id": ids["session"], "owner": ids["owner"]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'S7 synthetic branch')"
            ),
            {"id": ids["branch"], "code": ids["branch"].hex[:20]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'S7 synthetic territory')"
            ),
            {"id": ids["territory"], "code": ids["territory"].hex[:20]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,'S7 synthetic customer',:branch,:territory)"
            ),
            {
                "id": ids["customer"],
                "code": ids["customer"].hex[:30],
                "branch": ids["branch"],
                "territory": ids["territory"],
            },
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'S7 synthetic product',0,0)"
            ),
            {"id": ids["product"], "sku": ids["product"].hex},
        )
    auth = {"Authorization": "Bearer " + str(ids["session"])}
    gate = Barrier(2)

    def submit(day, current):
        payload = {
            "customer_id": str(ids["customer"]),
            "visit_date": date(2026, 10, day).isoformat(),
            "lines": [
                {
                    "product_id": str(ids["product"]),
                    "quantity_prev": "20.125",
                    "quantity_current": current,
                }
            ],
        }
        with TestClient(app) as client:
            gate.wait(timeout=10)
            response = client.post("/visits", headers=auth, json=payload)
            assert response.status_code == 201, response.text
            return response.json()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            old_task = pool.submit(submit, 14, "12.125")
            new_task = pool.submit(submit, 15, "8.125")
            older, latest = old_task.result(timeout=20), new_task.result(timeout=20)
        with engine.connect() as db:
            # Not the request session or an enclosing test savepoint.
            rows = db.execute(
                text(
                    "SELECT quantity_on_hand,last_visit_id FROM sales.customer_held_stock WHERE customer_id=:customer"
                ),
                {"customer": ids["customer"]},
            ).all()
            assert rows == [(Decimal("8.125"), UUID(latest["id"]))]
            audit = db.execute(
                text(
                    "SELECT action,actor_user_id,new_values FROM audit.audit_log WHERE entity_type='stock_visit' AND actor_user_id=:owner"
                ),
                {"owner": ids["owner"]},
            ).all()
            assert len(audit) == 2
            assert all(
                row.action == "created"
                and row.actor_user_id == ids["owner"]
                and len(row.new_values["lines"]) == 1
                for row in audit
            )
            assert (
                db.execute(
                    text(
                        "SELECT count(*) FROM finance.ar_entry WHERE customer_id=:customer"
                    ),
                    {"customer": ids["customer"]},
                ).scalar_one()
                == 0
            )
        with TestClient(app) as client:
            assert (
                client.delete("/visits/" + latest["id"], headers=auth).status_code
                == 200
            )
            with engine.connect() as db:
                assert db.execute(
                    text(
                        "SELECT quantity_on_hand,last_visit_id FROM sales.customer_held_stock WHERE customer_id=:customer"
                    ),
                    {"customer": ids["customer"]},
                ).all() == [(Decimal("12.125"), UUID(older["id"]))]
            assert (
                client.delete("/visits/" + older["id"], headers=auth).status_code == 200
            )
        with engine.connect() as db:
            assert (
                db.execute(
                    text(
                        "SELECT count(*) FROM sales.customer_held_stock WHERE customer_id=:customer"
                    ),
                    {"customer": ids["customer"]},
                ).scalar_one()
                == 0
            )
            assert (
                db.execute(
                    text(
                        "SELECT count(*) FROM audit.audit_log WHERE entity_type='stock_visit' AND action='deleted' AND actor_user_id=:owner"
                    ),
                    {"owner": ids["owner"]},
                ).scalar_one()
                == 2
            )
    finally:
        # Remove only this fixture's mutable rows; immutable actor/audit history survives until runner DROP.
        with engine.begin() as db:
            db.execute(
                text("DELETE FROM sales.customer_held_stock WHERE customer_id=:id"),
                {"id": ids["customer"]},
            )
            db.execute(
                text("DELETE FROM sales.customer_stock_visit WHERE customer_id=:id"),
                {"id": ids["customer"]},
            )
            db.execute(
                text("DELETE FROM master_data.master_customer WHERE id=:id"),
                {"id": ids["customer"]},
            )
            db.execute(
                text("DELETE FROM master_data.master_product WHERE id=:id"),
                {"id": ids["product"]},
            )
            db.execute(
                text("DELETE FROM master_data.master_branch WHERE id=:id"),
                {"id": ids["branch"]},
            )
            db.execute(
                text("DELETE FROM master_data.master_territory WHERE id=:id"),
                {"id": ids["territory"]},
            )
            db.execute(
                text("DELETE FROM platform.platform_session WHERE id=:id"),
                {"id": ids["session"]},
            )
            db.execute(
                text("UPDATE platform.platform_user SET is_active=false WHERE id=:id"),
                {"id": ids["owner"]},
            )
