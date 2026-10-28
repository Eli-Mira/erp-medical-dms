"""Real shipped stock-visit PWA must persist to the disposable PostgreSQL server."""

from decimal import Decimal
from uuid import uuid4

from playwright.sync_api import expect
from sqlalchemy import text
from test_customer_pwa import _browser_user, references
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


def visits_page(page, width):
    if width < 1024:
        page.locator("#menu-toggle").click()
    page.locator('#sidebar [data-view="visits"]').click()
    expect(page.locator("#visits-view")).to_be_visible()


def test_visit_form_saves_to_server_and_survives_reload(live_app):
    with _browser_user(live_app, lang="en", width=390) as (page, engine, owner):
        branch, territory = references(engine)
        customer, product = uuid4(), uuid4()
        try:
            with engine.begin() as db:
                db.execute(
                    text(
                        "INSERT INTO master_data.master_customer(id,code,name_ar,name_en,branch_id,territory_id) VALUES (:id,:code,'عميل زيارة المتصفح','Visit browser customer',:b,:t)"
                    ),
                    {
                        "id": customer,
                        "code": customer.hex[:30],
                        "b": branch,
                        "t": territory,
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO master_data.master_product(id,sku,name_ar,name_en,base_price,vat_rate) VALUES (:id,:sku,'صنف زيارة المتصفح','Visit browser product',0,0)"
                    ),
                    {"id": product, "sku": product.hex},
                )
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#home-view")).to_be_visible()
            visits_page(page, 390)
            page.locator("#visit-customer").select_option(str(customer))
            page.locator("#visit-product").select_option(str(product))
            page.locator("#visit-prev").fill("10.125")
            page.locator("#visit-del").fill("5.250")
            page.locator("#visit-ret").fill("1.125")
            page.locator("#visit-cur").fill("8.125")
            page.locator("#visit-amount").fill("25.50")
            page.locator("#visit-notes").fill("S8 persisted visit")
            page.locator("#visit-save").click()
            expect(page.locator("#visit-warn")).to_contain_text(
                "Visit saved on server."
            )
            with engine.connect() as db:
                row = db.execute(
                    text(
                        "SELECT v.id,v.rep_id,v.created_by,l.quantity_prev,l.sell_through,l.amount FROM sales.customer_stock_visit v JOIN sales.customer_stock_visit_line l ON l.visit_id=v.id WHERE v.customer_id=:c AND l.product_id=:p"
                    ),
                    {"c": customer, "p": product},
                ).one()
                assert row.rep_id == row.created_by == owner
                assert row.quantity_prev == Decimal("10.125")
                assert row.sell_through == Decimal("6.125")
                assert row.amount == Decimal("25.50")
                assert (
                    db.execute(
                        text(
                            "SELECT count(*) FROM finance.ar_entry WHERE customer_id=:c"
                        ),
                        {"c": customer},
                    ).scalar_one()
                    == 0
                )
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#home-view")).to_be_visible()
            visits_page(page, 390)
            expect(
                page.locator('#visit-rows tr[data-visit-id="' + str(row.id) + '"]')
            ).to_contain_text("عميل زيارة المتصفح")
            expect(page.locator("#visit-rows")).to_contain_text("6.125")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        finally:
            # Only exact mutable fixture records; immutable visit audits remain until runner cleanup.
            with engine.begin() as db:
                db.execute(
                    text("DELETE FROM sales.customer_held_stock WHERE customer_id=:c"),
                    {"c": customer},
                )
                db.execute(
                    text("DELETE FROM sales.customer_stock_visit WHERE customer_id=:c"),
                    {"c": customer},
                )
                db.execute(
                    text("DELETE FROM master_data.master_customer WHERE id=:c"),
                    {"c": customer},
                )
                db.execute(
                    text("DELETE FROM master_data.master_product WHERE id=:p"),
                    {"p": product},
                )
                db.execute(
                    text("DELETE FROM master_data.master_branch WHERE id=:b"),
                    {"b": branch},
                )
                db.execute(
                    text("DELETE FROM master_data.master_territory WHERE id=:t"),
                    {"t": territory},
                )
