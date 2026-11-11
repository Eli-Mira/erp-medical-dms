"""Synthetic scoped API rows rendered by the real bilingual stock screen."""

import json
import os
import re
from pathlib import Path

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
    assert os.environ.get("APP_ENV") == "test" and Path("/.dockerenv").is_file()
    assert target.host == "127.0.0.1" and target.port == 5432
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", target.database or "")
    assert engine.url == target and POSTING_ENABLED is False
    with engine.connect() as db:
        assert db.scalar(text("SELECT current_database()")) == target.database
    yield
    engine.dispose()


@pytest.mark.parametrize("lang,width", [("ar", 390), ("en", 1440)])
def test_stock_batch_expiry_unbatched_and_empty(live_app, lang, width, request):
    with _browser_user(live_app, lang=lang, width=width) as (page, _engine, _user):
        rows = [
            {"warehouse_id": "w", "product_id": "p", "batch_id": "b", "quantity": "2", "updated_at": "2026-11-10", "warehouse_name": "Synthetic warehouse", "product_name": "Synthetic product"},
            {"warehouse_id": "w", "product_id": "p", "batch_id": None, "quantity": "1", "updated_at": "2026-11-10"},
        ]
        batch_no = "<img src=x onerror=alert(1)>"
        batches = [{"id": "b", "warehouse_id": "w", "product_id": "p", "batch_no": batch_no, "expiry_date": "2028-10-15"}]
        requests = []

        def stock(route):
            requests.append(route.request.url)
            route.fulfill(content_type="application/json", body=json.dumps(rows))

        page.route("**/inventory/stock", stock)
        page.route("**/inventory/batches", lambda route: route.fulfill(content_type="application/json", body=json.dumps(batches)))
        if width < 1024:
            page.locator("#menu-toggle").click()
        page.locator('#sidebar [data-view="inventory"]').click()
        expect(page.locator("#inventory-view")).to_be_visible()
        if page.locator("#menu-toggle").get_attribute("aria-expanded") == "true":
            page.locator("#menu-toggle").click()
        expect(page.locator("#stock-rows tr")).to_have_count(2)
        expect(page.locator("#stock-rows tr").first).to_contain_text(batch_no, timeout=3000)
        expect(page.locator("#stock-rows tr").first).to_contain_text("2028-10-15")
        expect(page.locator("#stock-rows img")).to_have_count(0)
        expect(page.locator("#stock-rows tr").nth(1).locator("td")).to_have_count(6)
        expect(page.locator("#stock-rows tr").nth(1).locator("td").nth(2)).to_have_text("—")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(Path(request.config.option.xmlpath).parent / (lang + "-stock-batch.png")))
        rows.clear()
        with page.expect_response(lambda response: response.url.endswith("/inventory/stock")):
            page.locator('[data-refresh="inventory"]').click()
        expect(page.locator("#stock-rows tr")).to_have_count(1)
        expect(page.locator("#stock-rows td")).to_have_attribute("colspan", "6")
        assert requests
