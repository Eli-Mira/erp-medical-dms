"""Sales targets: upsert + rep self-scoping + actuals from posted lines only."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text

pytest_plugins = ["test_invoice_api"]


def _month_start():
    return datetime.now(UTC).astimezone().date().replace(day=1)


def _target_payload(ids, *, rep="other", product=None, month=None, qty="100"):
    month = month or _month_start()
    return {
        "rep_id": str(ids[rep]),
        "product_id": None if product is None else str(ids[product]),
        "period_month": month.isoformat(),
        "target_quantity": qty,
    }


def _seed_posted_sale(db, ids, *, rep, product, qty, day_of_month, seq=1):
    """Direct Draft-insert + line, then Draft->Posted update, like real posting."""
    invoice_id = uuid4()
    db.execute(
        text("""INSERT INTO sales.sales_invoice
            (id, invoice_no, branch_id, warehouse_id, customer_id, rep_id,
             invoice_date, posting_status, created_by, territory_id,
             total_net, vat_amount, grand_total)
            VALUES (:id, :no, :branch, :wh, :cust, :rep, :date, 'Draft',
                    :owner, :terr, 0, 0, 0)"""),
        {"id": invoice_id, "no": f"TG-{seq}", "branch": ids["branch"],
         "wh": ids["warehouse"], "cust": ids["customer"], "rep": rep,
         "date": _month_start().replace(day=min(day_of_month, 28)),
         "owner": ids["owner"], "terr": ids["territory"]},
    )
    db.execute(
        text("""INSERT INTO sales.sales_invoice_line
            (id, invoice_id, product_id, line_no, quantity, unit_price,
             discount_pct, net_price, line_total, vat_rate, vat_amount)
            VALUES (gen_random_uuid(), :invoice, :product, 1, :qty, 10.00,
                    0, 10.00, :lt, 14.00, 0)"""),
        {"invoice": invoice_id, "product": product, "qty": Decimal(qty),
         "lt": Decimal(qty) * Decimal("10.00")},
    )
    db.execute(
        text("""UPDATE sales.sales_invoice SET posting_status='Posted',
            posted_at=now(), posted_by=:owner WHERE id=:id"""),
        {"owner": ids["owner"], "id": invoice_id},
    )


def test_owner_upsert_set_and_replace(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    payload = _target_payload(ids)
    first = client.post("/targets", headers=headers("owner"), json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["target_quantity"] == "100.000"
    assert first.json()["actual_quantity"] is None  # nothing posted yet

    payload["target_quantity"] = "250"
    second = client.post("/targets", headers=headers("owner"), json=payload)
    assert second.status_code == 201, second.text
    body = client.get("/targets", headers=headers("owner")).json()
    assert len(body) == 1 and body[0]["target_quantity"] == "250.000"
    events = db.execute(text("SELECT action, new_values::text FROM audit.audit_log "
                             "WHERE entity_type='sales_target' ORDER BY created_at")).all()
    assert [e[0] for e in events] == ["upserted", "upserted"]
    assert "250" in events[1][1]


def test_product_and_book_targets_can_coexist(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    assert client.post("/targets", headers=headers("owner"),
                       json=_target_payload(ids, qty="120")).status_code == 201
    assert client.post("/targets", headers=headers("owner"),
                       json=_target_payload(ids, product="product",
                                            qty="80")).status_code == 201
    body = client.get("/targets", headers=headers("owner")).json()
    assert len(body) == 2


def test_medical_rep_sees_only_own_rows(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["other_rep"] = uuid4()
    db.execute(text(
        "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
        "VALUES (:id,:u,'unused','medical_rep',false)"),
        {"id": ids["other_rep"], "u": f"tg_rep_{ids['other_rep'].hex}"})
    db.commit()
    assert client.post("/targets", headers=headers("owner"),
                       json=_target_payload(ids, rep="other",
                                            qty="100")).status_code == 201
    assert client.post("/targets", headers=headers("owner"),
                       json=_target_payload(ids, rep="other_rep",
                                            qty="200")).status_code == 201
    own = client.get("/targets", headers=headers("other")).json()
    assert len(own) == 1, own
    assert own[0]["rep_id"] == str(ids["other"])


def test_actuals_from_posted_lines_book_and_product(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    _seed_posted_sale(db, ids, rep=ids["other"], product=ids["product"],
                      qty="30", day_of_month=10, seq=1)
    _seed_posted_sale(db, ids, rep=ids["other"], product=ids["exempt"],
                      qty="20", day_of_month=15, seq=2)
    db.commit()
    client.post("/targets", headers=headers("owner"),
                json=_target_payload(ids, product="product", qty="25"))
    client.post("/targets", headers=headers("owner"),
                json=_target_payload(ids, qty="40"))
    rows = {r["product_id"]: r for r in
            client.get("/targets", headers=headers("owner")).json()}
    # Draft-only or other-month sales never leak: nothing else was seeded.
    assert Decimal(rows[str(ids["product"])]["actual_quantity"]) == 30
    assert Decimal(rows[None]["actual_quantity"]) == 50  # whole book


def test_manage_validation(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    ids["staff"] = uuid4()
    db.execute(text(
        "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
        "VALUES (:id,:u,'unused','warehouse_staff',false)"),
        {"id": ids["staff"], "u": f"tg_staff_{ids['staff'].hex}"})
    db.commit()
    assert client.post("/targets", headers=headers("owner"),
                       json=_target_payload(ids, rep="staff")).status_code == 422
    assert client.post("/targets", headers=headers("owner"),
                       json=_target_payload(ids, product="exempt",
                                            qty="10")).status_code == 201
    payload = _target_payload(ids, qty="5")
    payload["product_id"] = str(uuid4())  # unknown product
    assert client.post("/targets", headers=headers("owner"),
                       json=payload).status_code == 422


def test_role_gating(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    assert client.post("/targets", headers=headers("other"),  # medical_rep
                       json=_target_payload(ids)).status_code == 403
    assert client.get("/targets", headers=headers("owner")).status_code == 200
    assert client.get("/targets").status_code == 401
