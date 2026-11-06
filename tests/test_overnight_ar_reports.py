"""AR customer statements and aging: real PostgreSQL, no mocks."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture
def ar_report_env():
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {name: uuid4() for name in (
        "owner", "other", "branch", "other_branch", "territory", "other_territory",
        "customer", "other_customer", "territory_customer", "reason")}
    for role, uid, owner in (("owner", ids["owner"], True), ("finance", ids["other"], False)):
        db.execute(text(
            "INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) "
            "VALUES (:id,:u,'unused',:role,:owner)"),
            {"id": uid, "u": f"ar_rep_{uid.hex}", "role": role, "owner": owner})
    for key in ("branch", "other_branch"):
        db.execute(text(
            "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Test branch')"),
            {"id": ids[key], "code": ids[key].hex[:20]})
    for key in ("territory", "other_territory"):
        db.execute(text(
            "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'Test territory')"),
            {"id": ids[key], "code": ids[key].hex[:20]})
    for key, branch, terr in (("customer", "branch", "territory"),
                              ("other_customer", "other_branch", "territory"),
                              ("territory_customer", "branch", "other_territory")):
        db.execute(text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
            "VALUES (:id,:code,'Test customer',:branch,:terr)"),
            {"id": ids[key], "code": ids[key].hex[:30], "branch": ids[branch],
             "terr": ids[terr]})
    db.execute(text(
        "INSERT INTO audit.reason_code(id,code,category) VALUES (:id,:code,'adjustment')"),
        {"id": ids["reason"], "code": ids["reason"].hex[:30]})
    db.commit()

    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        def headers(user="owner"):
            sid = uuid4()
            db.execute(text(
                "INSERT INTO platform.platform_session(id,user_id,expires_at) "
                "VALUES (:sid,:uid,now() + interval '1 hour')"),
                {"sid": sid, "uid": ids[user]})
            db.commit()
            return {"Authorization": f"Bearer {sid}"}

        def seed(*, customer="customer", entry_type="opening", debit="0.00",
                 credit="0.00", entry_date, due_date=None, note=None):
            return db.execute(text("""
                INSERT INTO finance.ar_entry
                    (customer_id, invoice_id, entry_type, entry_date, due_date,
                     debit, credit, reason_id, note, created_by)
                VALUES (:c, NULL, :et, :d, :due, :debit, :credit, NULL, :note, :actor)
                RETURNING id
            """), {
                "c": ids[customer], "et": entry_type, "d": entry_date, "due": due_date,
                "debit": debit, "credit": credit, "note": note, "actor": ids["owner"],
            }).scalar()

        yield client, db, ids, headers, seed
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def test_statement_requires_authentication(ar_report_env):
    client = ar_report_env[0]
    assert client.get(f"/ar/statements/{uuid4()}").status_code == 401


def test_statement_running_balance_and_opening(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="100.00", entry_date=date(2026, 1, 1),
         due_date=date(2026, 1, 31))
    seed(entry_type="payment", credit="40.00", entry_date=date(2026, 1, 15))
    seed(entry_type="opening", debit="7.00", entry_date=date(2026, 1, 20))
    body = client.get(
        f"/ar/statements/{ids['customer']}?date_from=2026-01-01&date_to=2026-02-01",
        headers=headers()).json()
    assert body["opening_balance"] == "0"
    assert body["total_debit"] == "107.00"
    assert body["total_credit"] == "40.00"
    assert body["closing_balance"] == "67.00"
    assert [line["entry_date"] for line in body["lines"]] == [
        "2026-01-01", "2026-01-15", "2026-01-20"]
    assert [line["balance"] for line in body["lines"]] == ["100.00", "60.00", "67.00"]


def test_statement_opening_balance_before_range(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="50.00", entry_date=date(2025, 12, 31))
    seed(entry_type="opening", debit="20.00", entry_date=date(2026, 1, 2))
    body = client.get(
        f"/ar/statements/{ids['customer']}?date_from=2026-01-01&date_to=2026-02-01",
        headers=headers()).json()
    assert body["opening_balance"] == "50.00"
    assert body["closing_balance"] == "70.00"
    assert [line["entry_date"] for line in body["lines"]] == ["2026-01-02"]


def test_statement_month_boundary_excludes_upper_date(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="1.00", entry_date=date(2026, 1, 31))
    seed(entry_type="opening", debit="2.00", entry_date=date(2026, 2, 1))
    body = client.get(
        f"/ar/statements/{ids['customer']}?date_from=2026-01-01&date_to=2026-02-01",
        headers=headers()).json()
    assert body["closing_balance"] == "1.00"
    assert [line["entry_date"] for line in body["lines"]] == ["2026-01-31"]


def test_statement_empty_and_future_range(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    body = client.get(f"/ar/statements/{ids['customer']}", headers=headers()).json()
    assert body["opening_balance"] == "0"
    assert body["lines"] == []
    assert body["closing_balance"] == "0"
    seed(entry_type="opening", debit="5.00", entry_date=date(2026, 3, 1))
    body = client.get(
        f"/ar/statements/{ids['customer']}?date_from=2026-01-01&date_to=2026-02-01",
        headers=headers()).json()
    assert body["lines"] == []
    assert body["opening_balance"] == "0"
    assert body["closing_balance"] == "0"


def test_statement_exact_decimals_no_rounding(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="100.01", entry_date=date(2026, 1, 1))
    seed(entry_type="payment", credit="0.03", entry_date=date(2026, 1, 2))
    body = client.get(f"/ar/statements/{ids['customer']}", headers=headers()).json()
    assert body["closing_balance"] == "99.98"


def test_statement_unknown_customer_404(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    response = client.get(f"/ar/statements/{uuid4()}", headers=headers())
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_statement_out_of_scope_customer_404(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    db.execute(text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
               {"id": ids["other"]})
    db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
               {"u": ids["other"], "b": ids["branch"]})
    db.commit()
    auth = headers("other")
    assert client.get(f"/ar/statements/{ids['customer']}", headers=auth).status_code == 200
    assert client.get(f"/ar/statements/{ids['other_customer']}", headers=auth).status_code == 404


@pytest.mark.parametrize("role", ["owner", "finance", "sales_manager", "district_manager",
                                  "read_only_auditor"])
def test_statement_read_roles(ar_report_env, role):
    client, db, ids, headers, seed = ar_report_env
    if role != "owner":
        db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"),
                   {"r": role, "id": ids["other"]})
        if role in ("sales_manager", "district_manager"):
            db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
                       {"u": ids["other"], "b": ids["branch"]})
        db.commit()
        auth = headers("other")
    else:
        auth = headers()
    assert client.get(f"/ar/statements/{ids['customer']}", headers=auth).status_code == 200


@pytest.mark.parametrize("role", ["warehouse_staff", "medical_rep", "admin"])
def test_statement_denied_for_non_read_roles(ar_report_env, role):
    client, db, ids, headers, seed = ar_report_env
    db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"),
               {"r": role, "id": ids["other"]})
    db.commit()
    assert client.get(f"/ar/statements/{ids['customer']}", headers=headers("other")).status_code == 403


def test_aging_requires_authentication(ar_report_env):
    client = ar_report_env[0]
    assert client.get("/ar/aging").status_code == 401


def test_aging_bucket_boundaries(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="1.00", entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="2.00", entry_date=as_of,
         due_date=as_of - timedelta(days=1))
    seed(entry_type="opening", debit="3.00", entry_date=as_of,
         due_date=as_of - timedelta(days=30))
    seed(entry_type="opening", debit="4.00", entry_date=as_of,
         due_date=as_of - timedelta(days=31))
    seed(entry_type="opening", debit="5.00", entry_date=as_of,
         due_date=as_of - timedelta(days=60))
    seed(entry_type="opening", debit="6.00", entry_date=as_of,
         due_date=as_of - timedelta(days=61))
    seed(entry_type="opening", debit="7.00", entry_date=as_of,
         due_date=as_of - timedelta(days=90))
    seed(entry_type="opening", debit="8.00", entry_date=as_of,
         due_date=as_of - timedelta(days=91))
    seed(entry_type="opening", debit="9.00", entry_date=as_of, due_date=None)
    body = client.get(f"/ar/aging?as_of={as_of.isoformat()}", headers=headers()).json()
    row = next(c for c in body["customers"] if c["customer_id"] == str(ids["customer"]))
    assert row["current"] == "1.00"
    assert row["d1_30"] == "5.00"
    assert row["d31_60"] == "9.00"
    assert row["d61_90"] == "13.00"
    assert row["over_90"] == "8.00"
    assert row["undated"] == "9.00"
    assert row["total"] == "45.00"


def test_aging_credit_reduces_its_due_bucket(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="100.00", entry_date=as_of,
         due_date=as_of - timedelta(days=10))
    seed(entry_type="payment", credit="30.00", entry_date=as_of,
         due_date=as_of - timedelta(days=10))
    body = client.get(f"/ar/aging?as_of={as_of.isoformat()}", headers=headers()).json()
    row = next(c for c in body["customers"] if c["customer_id"] == str(ids["customer"]))
    assert row["d1_30"] == "70.00"
    assert row["total"] == "70.00"


def test_aging_sum_reconciles_to_balance(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="100.00", entry_date=as_of,
         due_date=as_of - timedelta(days=45))
    seed(entry_type="payment", credit="25.00", entry_date=as_of,
         due_date=as_of - timedelta(days=45))
    seed(entry_type="opening", debit="10.00", entry_date=as_of, due_date=None)
    body = client.get(f"/ar/aging?as_of={as_of.isoformat()}", headers=headers()).json()
    row = next(c for c in body["customers"] if c["customer_id"] == str(ids["customer"]))
    buckets = sum(Decimal(row[name]) for name in
                  ("current", "d1_30", "d31_60", "d61_90", "over_90", "undated"))
    assert buckets == Decimal(row["total"])
    balance = client.get(f"/ar/balances?customer_id={ids['customer']}", headers=headers()).json()
    assert Decimal(row["total"]) == Decimal(balance[0]["balance"])


def test_aging_empty_and_future_due_dates(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    body = client.get(f"/ar/aging?as_of={date(2026, 11, 6).isoformat()}",
                      headers=headers()).json()
    # The disposable DB is shared with other modules: assert only about ours.
    assert all(c["customer_id"] != str(ids["customer"]) for c in body["customers"])
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="12.00", entry_date=as_of,
         due_date=as_of + timedelta(days=10))
    body = client.get(f"/ar/aging?as_of={as_of.isoformat()}", headers=headers()).json()
    row = next(c for c in body["customers"] if c["customer_id"] == str(ids["customer"]))
    assert row["current"] == "12.00"
    assert row["total"] == "12.00"


def test_aging_unknown_customer_404(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    response = client.get(f"/ar/aging?customer_id={uuid4()}", headers=headers())
    assert response.status_code == 404


def test_aging_out_of_scope_customer_404(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    db.execute(text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
               {"id": ids["other"]})
    db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
               {"u": ids["other"], "b": ids["branch"]})
    db.commit()
    auth = headers("other")
    assert client.get(f"/ar/aging?customer_id={ids['customer']}", headers=auth).status_code == 200
    assert client.get(f"/ar/aging?customer_id={ids['other_customer']}", headers=auth).status_code == 404


def test_aging_branch_scoped_sees_only_assigned_branch(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="10.00", entry_date=date(2026, 11, 1),
         due_date=date(2026, 11, 1))
    seed(entry_type="opening", debit="99.00", customer="other_customer",
         entry_date=date(2026, 11, 1), due_date=date(2026, 11, 1))
    db.execute(text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"),
               {"id": ids["other"]})
    db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"),
               {"u": ids["other"], "b": ids["branch"]})
    db.commit()
    body = client.get(f"/ar/aging?as_of={date(2026, 11, 6).isoformat()}",
                      headers=headers("other")).json()
    assert [c["customer_id"] for c in body["customers"]] == [str(ids["customer"])]
    assert body["customers"][0]["total"] == "10.00"


@pytest.mark.parametrize("role", ["owner", "finance", "sales_manager", "district_manager",
                                  "read_only_auditor"])
def test_aging_read_roles(ar_report_env, role):
    client, db, ids, headers, seed = ar_report_env
    if role != "owner":
        db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"),
                   {"r": role, "id": ids["other"]})
        db.commit()
        auth = headers("other")
    else:
        auth = headers()
    assert client.get("/ar/aging", headers=auth).status_code == 200


@pytest.mark.parametrize("role", ["warehouse_staff", "medical_rep", "admin"])
def test_aging_denied_for_non_read_roles(ar_report_env, role):
    client, db, ids, headers, seed = ar_report_env
    db.execute(text("UPDATE platform.platform_user SET role=:r WHERE id=:id"),
               {"r": role, "id": ids["other"]})
    db.commit()
    assert client.get("/ar/aging", headers=headers("other")).status_code == 403


def test_aging_territory_filter_excludes_other_territories(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="10.00", entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="20.00", customer="other_customer",
         entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="99.00", customer="territory_customer",
         entry_date=as_of, due_date=as_of)
    body = client.get(
        f"/ar/aging?as_of={as_of.isoformat()}&territory_id={ids['territory']}",
        headers=headers()).json()
    assert {c["customer_id"] for c in body["customers"]} == {
        str(ids["customer"]), str(ids["other_customer"])}
    unfiltered = client.get(f"/ar/aging?as_of={as_of.isoformat()}",
                            headers=headers()).json()
    assert {c["customer_id"] for c in unfiltered["customers"]} >= {
        str(ids["customer"]), str(ids["territory_customer"])}


def test_balances_territory_filter_excludes_other_territories(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="10.00", entry_date=date(2026, 1, 1))
    seed(entry_type="opening", debit="99.00", customer="territory_customer",
         entry_date=date(2026, 1, 1))
    rows = client.get(f"/ar/balances?territory_id={ids['territory']}",
                      headers=headers()).json()
    assert {r["customer_id"] for r in rows} == {
        str(ids["customer"]), str(ids["other_customer"])}


def test_statement_matches_independent_window_sql(ar_report_env):
    """The API's running balance must equal an independent window-function SQL."""
    client, db, ids, headers, seed = ar_report_env
    seed(entry_type="opening", debit="100.00", entry_date=date(2026, 1, 1))
    seed(entry_type="payment", credit="40.00", entry_date=date(2026, 1, 15))
    seed(entry_type="opening", debit="7.50", entry_date=date(2026, 1, 20))
    independent = db.execute(text("""
        SELECT SUM(debit - credit) OVER (ORDER BY entry_date, id) AS balance
        FROM finance.ar_entry
        WHERE customer_id = :c AND entry_date >= :from AND entry_date < :to
        ORDER BY entry_date, id
    """), {"c": str(ids["customer"]), "from": date(2026, 1, 1),
          "to": date(2026, 2, 1)}).scalars().all()
    body = client.get(
        f"/ar/statements/{ids['customer']}?date_from=2026-01-01&date_to=2026-02-01",
        headers=headers()).json()
    assert [str(balance) for balance in independent] == [
        line["balance"] for line in body["lines"]]
    assert Decimal(str(independent[-1])) == Decimal(body["closing_balance"])


def test_aging_matches_independent_case_sql(ar_report_env):
    """Bucket totals must equal an independent FILTER/CASE SQL aggregation."""
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="1.00", entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="2.00", entry_date=as_of,
         due_date=as_of - timedelta(days=10))
    seed(entry_type="opening", debit="4.00", entry_date=as_of,
         due_date=as_of - timedelta(days=45))
    seed(entry_type="opening", debit="8.00", entry_date=as_of,
         due_date=as_of - timedelta(days=120))
    seed(entry_type="opening", debit="16.00", entry_date=as_of, due_date=None)
    independent = db.execute(text("""
        SELECT
          COALESCE(SUM(debit - credit) FILTER (WHERE due_date >= :as_of), 0) AS current,
          COALESCE(SUM(debit - credit) FILTER (WHERE due_date < :as_of AND due_date >= :as_of - 30), 0) AS d1_30,
          COALESCE(SUM(debit - credit) FILTER (WHERE due_date < :as_of - 30 AND due_date >= :as_of - 60), 0) AS d31_60,
          COALESCE(SUM(debit - credit) FILTER (WHERE due_date < :as_of - 60 AND due_date >= :as_of - 90), 0) AS d61_90,
          COALESCE(SUM(debit - credit) FILTER (WHERE due_date < :as_of - 90), 0) AS over_90,
          COALESCE(SUM(debit - credit) FILTER (WHERE due_date IS NULL), 0) AS undated
        FROM finance.ar_entry WHERE customer_id = :c
    """), {"c": str(ids["customer"]), "as_of": as_of}).mappings().one()
    body = client.get(
        f"/ar/aging?as_of={as_of.isoformat()}&customer_id={ids['customer']}",
        headers=headers()).json()
    row = next(c for c in body["customers"] if c["customer_id"] == str(ids["customer"]))
    for name in ("current", "d1_30", "d31_60", "d61_90", "over_90", "undated"):
        assert Decimal(row[name]) == Decimal(str(independent[name]))


def test_aging_excludes_entries_dated_after_as_of(ar_report_env):
    """An entry dated after the as-of date must not be aged, even with an old due date."""
    client, db, ids, headers, seed = ar_report_env
    as_of = date(2026, 11, 6)
    seed(entry_type="opening", debit="10.00", entry_date=as_of, due_date=as_of)
    seed(entry_type="opening", debit="999.00", entry_date=as_of + timedelta(days=1),
         due_date=as_of)
    body = client.get(f"/ar/aging?as_of={as_of.isoformat()}", headers=headers()).json()
    row = next(c for c in body["customers"] if c["customer_id"] == str(ids["customer"]))
    assert row["current"] == "10.00"
    assert row["total"] == "10.00"


def test_aging_labels_output_and_marks_rules_pending(ar_report_env):
    client, db, ids, headers, seed = ar_report_env
    body = client.get(f"/ar/aging?as_of={date(2026, 11, 6).isoformat()}",
                      headers=headers()).json()
    assert body["label"] == "ledger aging"
    assert "pending accountant approval" in body["note"].lower()
