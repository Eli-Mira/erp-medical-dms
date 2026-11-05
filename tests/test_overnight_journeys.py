"""Actual bilingual persona journeys; missing stock UI is a defect, not a waiver."""

from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from test_customer_pwa import _browser_user, customer_page, fill_customer, references
from test_lane2_balance_history_browser import (
    require_owned_database_before_module_seed as require_owned_database_before_module_seed,  # noqa: PLC0414
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


def nav(page, view, width):
    if (
        width < 1024
        and page.locator("#menu-toggle").get_attribute("aria-expanded") != "true"
    ):
        page.locator("#menu-toggle").click()
    control = page.locator(f'#sidebar [data-view="{view}"]')
    expect(control).to_be_visible()
    control.click()
    expect(page.locator(f"#{view}-view")).to_be_visible()
    if width < 1024:
        expect(page.locator("#menu-toggle")).to_have_attribute("aria-expanded", "false")


def picture(page, request):
    folder = Path(request.config.option.xmlpath).parent / "journey-screenshots"
    folder.mkdir(exist_ok=True)
    page.screenshot(path=str(folder / (request.node.name + ".png")), full_page=False)


@pytest.mark.parametrize(
    "lang,width", [("ar", 390), ("en", 1440)], ids=["ar390", "en1440"]
)
def test_owner_customer_save_edit_reopen_and_real_territory_target(
    live_app, lang, width, request
):
    branch, territory = references(live_app[1])
    product, target = uuid4(), uuid4()
    with _browser_user(live_app, lang=lang, width=width) as (page, engine, owner):
        customer_page(page, width)
        page.locator("#customer-add").click()
        code = "E18-" + uuid4().hex[:14]
        fill_customer(page, branch, territory, code)
        with page.expect_response(
            lambda r: (
                urlsplit(r.url).path == "/master/customers"
                and r.request.method == "POST"
            )
        ) as saved:
            page.locator("#customer-save").click()
        assert saved.value.status == 201
        customer = saved.value.json()["id"]
        expect(page.locator("#customer-dialog")).to_be_hidden()
        row = page.locator(f'tr[data-customer-id="{customer}"]')
        expect(row).to_contain_text(code)
        row.locator("[data-customer-edit]").click()
        page.locator("#customer-name-ar").fill("عميل رحلة محفوظ")
        page.locator("#customer-name-en").fill("")
        with page.expect_response(
            lambda r: (
                urlsplit(r.url).path == "/master/customers/" + customer
                and r.request.method == "PATCH"
            )
        ) as changed:
            page.locator("#customer-save").click()
        assert changed.value.status == 200
        expect(page.locator("#customer-dialog")).to_be_hidden()
        with engine.begin() as witness:
            assert (
                witness.scalar(
                    text(
                        "SELECT name_ar FROM master_data.master_customer WHERE id=:id"
                    ),
                    {"id": customer},
                )
                == "عميل رحلة محفوظ"
            )
            witness.execute(
                text(
                    "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'E18 target product',114,14)"
                ),
                {"id": product, "sku": product.hex},
            )
            witness.execute(
                text(
                    "INSERT INTO sales.sales_target(id,territory_id,product_id,period_month,target_quantity,created_by) VALUES (:id,:territory,:product,:month,50,:actor)"
                ),
                {
                    "id": target,
                    "territory": territory,
                    "product": product,
                    "month": date(2026, 10, 1),
                    "actor": owner,
                },
            )
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        customer_page(page, width)
        row = page.locator(f'tr[data-customer-id="{customer}"]')
        expect(row).to_contain_text("عميل رحلة محفوظ")
        row.locator("[data-customer-edit]").click()
        expect(page.locator("#customer-name-ar")).to_have_value("عميل رحلة محفوظ")
        page.locator("#customer-cancel").click()
        with page.expect_response(
            lambda r: urlsplit(r.url).path == "/targets" and r.request.method == "GET"
        ) as listing:
            nav(page, "targets", width)
        assert listing.value.status == 200
        assert any(item["id"] == str(target) for item in listing.value.json())
        target_row = page.locator("#target-rows tr").filter(has_text=territory)
        expect(target_row).to_have_count(1)
        expect(target_row).to_contain_text("المنطقة" if lang == "ar" else "Territory")
        picture(page, request)


@pytest.mark.parametrize(
    "lang,width", [("ar", 390), ("en", 1440)], ids=["ar390", "en1440"]
)
def test_medical_rep_positive_customer_and_target_scope(live_app, lang, width, request):
    branch, territory = references(live_app[1])
    other_branch, other_territory = references(live_app[1])
    own, other, product = uuid4(), uuid4(), uuid4()
    with _browser_user(
        live_app, role="medical_rep", owner=False, lang=lang, width=width
    ) as (page, engine, user):
        with engine.begin() as seed:
            seed.execute(
                text(
                    "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"
                ),
                {"u": user, "b": branch},
            )
            seed.execute(
                text(
                    "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t)"
                ),
                {"u": user, "t": territory},
            )
            seed.execute(
                text(
                    "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,:name,:b,:t)"
                ),
                [
                    {
                        "id": own,
                        "code": own.hex[:30],
                        "name": "E18 visible customer",
                        "b": branch,
                        "t": territory,
                    },
                    {
                        "id": other,
                        "code": other.hex[:30],
                        "name": "E18 FOREIGN PRIVATE CANARY",
                        "b": other_branch,
                        "t": other_territory,
                    },
                ],
            )
            seed.execute(
                text(
                    "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'E18 rep product',114,14)"
                ),
                {"id": product, "sku": product.hex},
            )
            seed.execute(
                text(
                    "INSERT INTO sales.sales_target(rep_id,product_id,period_month,target_quantity,created_by) VALUES (:u,:p,:m,25,:u)"
                ),
                {"u": user, "p": product, "m": date(2026, 10, 1)},
            )
        with page.expect_response(
            lambda r: (
                urlsplit(r.url).path == "/master/customers"
                and r.request.method == "GET"
            )
        ) as listing:
            nav(page, "customers", width)
        assert listing.value.status == 200
        result_ids = {item["id"] for item in listing.value.json()}
        assert str(own) in result_ids and str(other) not in result_ids
        expect(page.locator(f'tr[data-customer-id="{own}"]')).to_be_visible()
        expect(page.locator(f'tr[data-customer-id="{other}"]')).to_have_count(0)
        expect(page.locator("#customers-view")).not_to_contain_text(
            "E18 FOREIGN PRIVATE CANARY"
        )
        expect(page.locator("#customer-add")).to_be_hidden()
        with page.expect_response(
            lambda r: urlsplit(r.url).path == "/targets" and r.request.method == "GET"
        ) as targets:
            nav(page, "targets", width)
        assert targets.value.status == 200
        assert targets.value.json() and all(
            item["rep_id"] == str(user) for item in targets.value.json()
        )
        expect(
            page.locator("#target-rows tr").filter(has_text=str(user))
        ).to_have_count(1)
        expect(page.locator("#who-role")).to_have_text(
            "مندوب مبيعات" if lang == "ar" else "Sales representative"
        )
        picture(page, request)


@pytest.mark.parametrize(
    "lang,width", [("ar", 390), ("en", 1440)], ids=["ar390", "en1440"]
)
def test_warehouse_positive_stock_api_has_a_usable_stock_screen(
    live_app, lang, width, request, record_property
):
    branch, _territory = references(live_app[1])
    warehouse, product = uuid4(), uuid4()
    with _browser_user(
        live_app, role="warehouse_staff", owner=False, lang=lang, width=width
    ) as (page, engine, user):
        with engine.begin() as seed:
            seed.execute(
                text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b) ON CONFLICT DO NOTHING"),
                {"u": user, "b": branch},
            )
            seed.execute(
                text(
                    "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:b,:c,'E18 warehouse')"
                ),
                {"id": warehouse, "b": branch, "c": warehouse.hex[:30]},
            )
            seed.execute(
                text(
                    "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'E18 warehouse product',114,14)"
                ),
                {"id": product, "sku": product.hex},
            )
            seed.execute(
                text(
                    "INSERT INTO inventory.stock_balance(warehouse_id,product_id,quantity) VALUES (:w,:p,10)"
                ),
                {"w": warehouse, "p": product},
            )
        token = page.evaluate("localStorage.getItem('token')")
        response = page.request.get(
            live_app[0] + "/inventory/stock?warehouse_id=" + str(warehouse),
            headers={"Authorization": "Bearer " + token},
        )
        assert response.status == 200
        assert any(item["product_id"] == str(product) for item in response.json())
        record_property("stock_api_status", response.status)
        record_property("warehouse_stock_ui_required", True)
        try:
            nav(page, "inventory", width)
            expect(page.locator("#inventory-view")).to_contain_text(
                "E18 warehouse product"
            )
        finally:
            picture(page, request)
