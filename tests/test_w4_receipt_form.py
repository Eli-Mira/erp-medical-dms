"""Bilingual receipt entry keeps the real default-OFF API guard intact."""

import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.engine import make_url
from test_customer_pwa import _browser_user
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


@pytest.fixture(scope="module", autouse=True)
def owned_database():
    from app.config import POSTING_ENABLED
    from app.db import engine

    target = make_url(os.environ["DATABASE_URL"])
    assert os.environ.get("APP_ENV") == "test"
    assert Path("/.dockerenv").is_file()
    assert target.host in {"localhost", "127.0.0.1", "::1"} and target.port == 5432
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", target.database or "")
    assert engine.url == target and POSTING_ENABLED is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT current_database()")) == target.database
    yield
    engine.dispose()


def seed_invoice(engine, owner):
    # Synthetic display fixture only: no posting function, flag change or AR write.
    ids = {
        key: uuid4()
        for key in ("branch", "territory", "customer", "warehouse", "invoice")
    }
    code = "W4-" + uuid4().hex[:12]
    with engine.begin() as db:
        for table, key in [("branch", "branch"), ("territory", "territory")]:
            db.execute(
                text(
                    f"INSERT INTO master_data.master_{table}(id,code,name_ar) VALUES (:id,:code,'Synthetic W4')"
                ),
                {"id": ids[key], "code": code},
            )
        db.execute(
            text(
                "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:customer,:code,'Synthetic W4',:branch,:territory)"
            ),
            {**ids, "code": code},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_warehouse(id,code,name_ar,branch_id) VALUES (:warehouse,:code,'Synthetic W4',:branch)"
            ),
            {**ids, "code": code},
        )
        db.execute(
            text(
                "INSERT INTO sales.sales_invoice(id,invoice_no,branch_id,warehouse_id,customer_id,territory_id,invoice_date,posting_status,posted_at,posted_by,created_by,version,total_before_discount,total_discount,total_net,vat_amount,grand_total) VALUES (:invoice,:code,:branch,:warehouse,:customer,:territory,CURRENT_DATE,'Posted',now(),:owner,:owner,3,100,0,100,0,100)"
            ),
            {**ids, "code": code, "owner": owner},
        )
    return str(ids["invoice"]), code


@pytest.mark.parametrize(
    "lang,width", [("ar", 390), ("en", 1440)], ids=["ar390", "en1440"]
)
def test_receipt_form_submits_decimal_and_preserves_default409(
    live_app, lang, width, request
):
    with _browser_user(live_app, lang=lang, width=width) as (page, engine, owner):
        invoice_id, invoice_no = seed_invoice(engine, owner)
        if width < 1024:
            page.locator("#menu-toggle").click()
        page.locator('#sidebar [data-view="collections"]').click()
        expect(page.locator("#collections-view")).to_be_visible()
        if page.locator("#menu-toggle").get_attribute("aria-expanded") == "true":
            page.locator("#menu-toggle").click()
        form = page.locator("#receipt-form")
        expect(form).to_be_visible(timeout=3000)
        expect(
            page.get_by_label("الفاتورة" if lang == "ar" else "Invoice", exact=True)
        ).to_be_visible()
        expect(
            page.locator(f'#receipt-invoice option[value="{invoice_id}"]')
        ).to_contain_text(invoice_no)
        page.locator("#receipt-invoice").select_option(invoice_id)
        page.locator("#receipt-number").fill("W4-" + lang)
        page.locator("#receipt-amount").fill("0.10")
        page.locator("#receipt-method").select_option("cash")
        page.locator("#receipt-note").fill("Synthetic default-OFF browser control")
        with engine.connect() as db:
            before = tuple(
                db.execute(
                    text(
                        "SELECT (SELECT count(*) FROM finance.payment_receipt), (SELECT count(*) FROM finance.ar_entry)"
                    )
                ).one()
            )
        with page.expect_response(
            lambda r: (
                urlsplit(r.url).path == "/collections" and r.request.method == "POST"
            )
        ) as response:
            page.locator("#receipt-save").click()
        assert response.value.status == 409
        payload = response.value.request.post_data_json
        assert payload["invoice_id"] == invoice_id
        assert payload["invoice_version"] == 3
        assert payload["amount"] == "0.10"
        assert set(payload) == {
            "invoice_id",
            "invoice_version",
            "receipt_no",
            "receipt_date",
            "amount",
            "method",
            "note",
        }
        expect(page.locator("#collections-error")).to_contain_text(
            response.value.json()["detail"]
        )
        expect(page.locator("#receipt-number")).to_have_value("W4-" + lang)
        expect(page.locator("#receipt-amount")).to_have_value("0.10")
        expect(page.locator("#receipt-save")).to_be_enabled()
        with engine.connect() as db:
            after = tuple(
                db.execute(
                    text(
                        "SELECT (SELECT count(*) FROM finance.payment_receipt), (SELECT count(*) FROM finance.ar_entry)"
                    )
                ).one()
            )
        assert after == before
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(
            path=str(
                Path(request.config.option.xmlpath).parent / (lang + "-receipt409.png")
            )
        )
