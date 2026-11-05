"""Bounded synthetic HTTP timing smoke; not a production-load/SLA certification."""

import json
from decimal import Decimal
from math import ceil
from statistics import median
from time import perf_counter
from uuid import uuid4

from sqlalchemy import text
from test_invoice_api import invoice_env as invoice_env  # noqa: PLC0414
from test_lane1_r22_territory_http import (
    require_owned_verifier_database as require_owned_verifier_database,  # noqa: PLC0414
)

from app import config

CUSTOMERS = 1000
PRODUCTS = 100
WAREHOUSES = 5
DRAFTS = 500
SAMPLES = 20


def test_realistic_synthetic_volume_http_timings(invoice_env, record_property):
    client, db, ids, payload, headers = invoice_env
    assert config.POSTING_ENABLED is False
    auth = headers("owner")
    products = [uuid4() for _ in range(PRODUCTS)]
    customers = [uuid4() for _ in range(CUSTOMERS)]
    warehouses = [uuid4() for _ in range(WAREHOUSES)]
    db.execute(
        text(
            "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) "
            "VALUES (:id,:code,'E14 synthetic product',114.00,14.00)"
        ),
        [{"id": value, "code": value.hex} for value in products],
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) "
            "VALUES (:id,:code,'E14 synthetic customer',:branch,:territory)"
        ),
        [
            {
                "id": value,
                "code": value.hex[:30],
                "branch": ids["branch"],
                "territory": ids["territory"],
            }
            for value in customers
        ],
    )
    db.execute(
        text(
            "INSERT INTO master_data.master_warehouse(id,code,name_ar,branch_id) "
            "VALUES (:id,:code,'E14 synthetic warehouse',:branch)"
        ),
        [
            {"id": value, "code": value.hex[:30], "branch": ids["branch"]}
            for value in warehouses
        ],
    )
    db.execute(
        text(
            "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) "
            "VALUES (:warehouse,:product,100.000)"
        ),
        [
            {"warehouse": warehouse, "product": product}
            for warehouse in warehouses
            for product in products
        ],
    )
    db.execute(
        text(
            "INSERT INTO finance.ar_entry(customer_id,entry_type,entry_date,debit,credit,created_by) "
            "VALUES (:customer,'opening',CURRENT_DATE,1000.01,0,:actor)"
        ),
        [{"customer": customer, "actor": ids["owner"]} for customer in customers],
    )
    db.commit()
    original = client.post("/invoices", json=payload, headers=auth)
    assert original.status_code == 201
    invoice_id = original.json()["id"]
    clones = [
        {"id": uuid4(), "number": "E14-" + uuid4().hex[:20], "source": invoice_id}
        for _ in range(DRAFTS - 1)
    ]
    db.execute(
        text(
            "INSERT INTO sales.sales_invoice "
            "(id,invoice_no,branch_id,territory_id,warehouse_id,customer_id,invoice_date,"
            "posting_status,created_by,total_before_discount,total_discount,total_net,vat_amount,grand_total) "
            "SELECT :id,:number,branch_id,territory_id,warehouse_id,customer_id,invoice_date,"
            "'Draft',created_by,total_before_discount,total_discount,total_net,vat_amount,grand_total "
            "FROM sales.sales_invoice WHERE id=:source"
        ),
        clones,
    )
    db.execute(
        text(
            "INSERT INTO sales.sales_invoice_line "
            "(invoice_id,line_no,product_id,batch_id,quantity,unit_price,discount_pct,net_price,line_total,vat_rate,vat_amount) "
            "SELECT :id,line_no,product_id,batch_id,quantity,unit_price,discount_pct,net_price,line_total,vat_rate,vat_amount "
            "FROM sales.sales_invoice_line WHERE invoice_id=:source"
        ),
        clones,
    )
    db.commit()
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM sales.sales_invoice WHERE posting_status='Posted'"
            )
        )
        == 0
    )
    assert (
        db.scalar(
            text(
                "SELECT count(*) FROM sales.sales_invoice WHERE posting_status='Draft'"
            )
        )
        == DRAFTS
    )
    assert (
        db.scalar(text("SELECT count(*) FROM inventory.stock_balance"))
        == PRODUCTS * WAREHOUSES
    )
    assert db.scalar(text("SELECT count(*) FROM finance.ar_entry")) == CUSTOMERS
    endpoints = [
        "/master/customers",
        "/master/products",
        "/master/warehouses",
        "/search?q=E14",
        "/inventory/stock",
        "/inventory/cover",
        "/invoices?limit=200",
        "/invoices?limit=20&offset=200",
        f"/invoices/{invoice_id}",
        "/invoices/report",
        "/reports/management-summary",
        "/ar/balances",
        "/ar/entries",
        "/collections",
    ]
    timings = []
    for path in endpoints:
        warm = client.get(path, headers=auth)
        assert warm.status_code == 200, path
        samples = []
        for _ in range(SAMPLES):
            start = perf_counter()
            response = client.get(path, headers=auth)
            elapsed = (perf_counter() - start) * 1000
            assert response.status_code == 200, path
            samples.append(elapsed)
        ordered = sorted(samples)
        timings.append(
            {
                "endpoint": "/invoices/{id}"
                if path == f"/invoices/{invoice_id}"
                else path,
                "samples_ms": samples,
                "sample_count": len(samples),
                "p50_ms": median(samples),
                "p95_nearest_rank_ms": ordered[ceil(0.95 * len(ordered)) - 1],
                "maximum_ms": max(samples),
            }
        )
    assert len(client.get("/master/customers", headers=auth).json()) >= CUSTOMERS
    assert len(client.get("/master/products", headers=auth).json()) >= PRODUCTS
    assert (
        len(client.get("/inventory/stock", headers=auth).json())
        == PRODUCTS * WAREHOUSES
    )
    listed = client.get("/invoices?limit=200", headers=auth).json()
    assert listed["total"] == DRAFTS and len(listed["items"]) == 200
    search = client.get("/search?q=E14", headers=auth).json()
    assert search["customers"] and search["products"]
    assert client.get("/collections", headers=auth).json() == []
    balances = client.get("/ar/balances", headers=auth).json()
    api_total = sum((Decimal(row["balance"]) for row in balances), Decimal(0))
    independent = db.scalar(
        text("SELECT COALESCE(sum(debit-credit),0) FROM finance.ar_entry")
    )
    assert api_total == independent == Decimal("1000.01") * CUSTOMERS
    assert client.post(f"/invoices/{invoice_id}/post", headers=auth).status_code == 409
    assert config.POSTING_ENABLED is False
    record_property(
        "performance_timings_json",
        json.dumps(
            {
                "kind": "ASGI_HTTP_REAL_POSTGRES_SYNTHETIC_BOUNDED_VOLUME_NOT_SLA",
                "seeded": {
                    "customers": CUSTOMERS,
                    "products": PRODUCTS,
                    "warehouses": WAREHOUSES,
                    "stock_balances": PRODUCTS * WAREHOUSES,
                    "draft_invoices": DRAFTS,
                    "draft_lines": DRAFTS,
                    "opening_ar_entries": CUSTOMERS,
                },
                "posting_default_off_http409": True,
                "limitations": [
                    "One owner and sequential warmed ASGI TestClient requests, no concurrent/live-network load",
                    "Draft-only invoices; posted financial aggregation and collections remain unmeasured",
                    "No throughput/SLA target approved; timings are observations, not SLA acceptance",
                ],
                "timings": timings,
            },
            separators=(",", ":"),
        ),
    )
