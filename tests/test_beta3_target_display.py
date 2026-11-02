"""New territory target API rows must retain identifiable scope in the UI."""

from urllib.parse import urlsplit

from playwright.sync_api import expect
from test_customer_pwa import _browser_user
from test_lane2_balance_history_browser import (
    require_owned_database_before_module_seed as require_owned_database_before_module_seed,  # noqa: PLC0414
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414
from test_zz_i1_browser import i1_dataset as i1_dataset  # noqa: PLC0414


def test_territory_target_table_exposes_its_real_scope(live_app, i1_dataset):
    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        token = page.evaluate("localStorage.getItem('token')")
        response = page.request.post(
            live_app[0] + "/targets",
            headers={"Authorization": "Bearer " + token},
            data={
                "territory_id": str(data["territory"]),
                "product_id": str(data["product"]),
                "period_month": "2026-10-01",
                "target_quantity": "50.000",
            },
        )
        assert response.status == 201
        created = response.json()
        assert created["rep_id"] is None
        assert created["territory_id"] == str(data["territory"])
        with page.expect_response(
            lambda r: urlsplit(r.url).path == "/targets" and r.request.method == "GET"
        ) as listed:
            page.locator('#sidebar [data-view="targets"]').click()
        assert listed.value.status == 200
        rows = listed.value.json()
        assert len(rows) == 1 and rows[0]["id"] == created["id"]
        row = page.locator("#target-rows tr")
        expect(row).to_have_count(1)
        expect(row.locator("td").nth(0)).to_contain_text(str(data["territory"]))
        expect(row.locator("td").nth(0)).to_contain_text("Territory")
        expect(page.locator("#targets-view thead th").first).to_have_text(
            "Representative / territory"
        )
