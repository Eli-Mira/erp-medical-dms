"""Integrated real-browser acceptance; synthetic ledgers remain until UUID DB drop."""

import json
import os
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from browser_readiness import wait_for_held
from fastapi.testclient import TestClient
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_customer_pwa import _browser_user
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


@pytest.fixture(scope="module")
def i1_dataset():
    from app.auth.repo import create_user
    from app.db import engine
    from app.finance.payments import create_receipt
    from app.main import app
    from app.sales.service import post_invoice_atomic

    assert os.environ.get("APP_ENV") == "test"
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", engine.url.database)
    ids = {
        k: uuid4()
        for k in (
            "owner",
            "branch",
            "territory",
            "warehouse",
            "product",
            "nohistory",
            "batch",
            "customer",
            "session",
        )
    }
    prefix = "I1-" + uuid4().hex[:10]
    today = datetime.now(UTC).date()
    with Session(engine) as db:
        assert db.scalar(text("SELECT current_database()")) == engine.url.database
        create_user(db, prefix, "Synthetic-I1-2026!", role="owner", is_owner=True)
        ids["owner"] = db.scalar(
            text("SELECT id FROM platform.platform_user WHERE username=:u"),
            {"u": prefix},
        )
        db.execute(
            text(
                "INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:id,:u,now()+interval '1 hour')"
            ),
            {"id": ids["session"], "u": ids["owner"]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_branch(id,code,name_ar,name_en) VALUES (:id,:c,'فرع التكامل','I1 branch')"
            ),
            {"id": ids["branch"], "c": prefix},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_territory(id,code,name_ar,name_en) VALUES (:id,:c,'منطقة التكامل','I1 territory')"
            ),
            {"id": ids["territory"], "c": prefix},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar,name_en) VALUES (:id,:b,:c,'مخزن التكامل','I1 warehouse')"
            ),
            {"id": ids["warehouse"], "b": ids["branch"], "c": prefix},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:c,'عميل التكامل',:b,:t)"
            ),
            {
                "id": ids["customer"],
                "c": prefix,
                "b": ids["branch"],
                "t": ids["territory"],
            },
        )
        for key in ("product", "nohistory"):
            db.execute(
                text(
                    "INSERT INTO master_data.master_product(id,sku,name_ar,name_en,base_price,vat_rate) VALUES (:id,:s,:n,:n,114,14)"
                ),
                {"id": ids[key], "s": prefix + key, "n": prefix + key},
            )
        db.execute(
            text(
                "INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date) VALUES (:id,:p,:w,:n,:d)"
            ),
            {
                "id": ids["batch"],
                "p": ids["product"],
                "w": ids["warehouse"],
                "n": prefix,
                "d": today + timedelta(days=365),
            },
        )
        db.execute(
            text(
                "INSERT INTO inventory.stock_balance(warehouse_id,product_id,batch_id,quantity) VALUES (:w,:p,:b,1000),(:w,:n,NULL,17)"
            ),
            {
                "w": ids["warehouse"],
                "p": ids["product"],
                "b": ids["batch"],
                "n": ids["nohistory"],
            },
        )
        db.commit()
    auth = {"Authorization": "Bearer " + str(ids["session"])}
    payload = {
        "invoice_no": prefix,
        "branch_id": str(ids["branch"]),
        "warehouse_id": str(ids["warehouse"]),
        "customer_id": str(ids["customer"]),
        "invoice_date": str(today),
        "lines": [
            {
                "product_id": str(ids["product"]),
                "batch_id": str(ids["batch"]),
                "quantity": "2",
                "discount_pct": "0",
            }
        ],
    }
    with TestClient(app) as client:
        response = client.post("/invoices", json=payload, headers=auth)
        assert response.status_code == 201, response.text
        invoice = response.json()
        with Session(engine) as db:
            post_invoice_atomic(db, invoice["id"], ids["owner"])
            db.commit()
            create_receipt(
                db,
                invoice_id=invoice["id"],
                branch_id=ids["branch"],
                customer_id=ids["customer"],
                receipt_no=prefix,
                receipt_date=today + timedelta(days=1),
                amount=Decimal(100),
                method="cash",
                note=None,
                actor_id=ids["owner"],
            )
            db.commit()
        draft = client.post(
            "/invoices", json={**payload, "invoice_no": prefix + "-D"}, headers=auth
        )
        assert draft.status_code == 201 and draft.json()["posting_status"] == "Draft"
        assert (
            client.post(
                "/invoices/" + draft.json()["id"] + "/post", headers=auth
            ).status_code
            == 409
        )
    return {
        **ids,
        "prefix": prefix,
        "today": today,
        "invoice": invoice["id"],
        "draft": draft.json()["id"],
        "engine": engine,
    }


def nav(page, view, width=1440):
    if (
        width < 1024
        and page.locator("#menu-toggle").get_attribute("aria-expanded") != "true"
    ):
        page.locator("#menu-toggle").click()
    page.locator(f'#sidebar [data-view="{view}"]').click()
    expect(page.locator(f"#{view}-view")).to_be_visible()


def test_i1_sql_oracles_match_actual_http_ledgers(live_app, i1_dataset):
    import httpx

    data = i1_dataset
    auth = {"Authorization": "Bearer " + str(data["session"])}
    with (
        httpx.Client(base_url=live_app[0], headers=auth) as client,
        data["engine"].connect() as db,
    ):
        report_response = client.get("/invoices/report")
        assert report_response.status_code == 200
        report = report_response.json()
        totals = (
            db.execute(
                text(
                    "SELECT count(*) AS invoice_count,COALESCE(SUM(total_net),0) AS total_net,COALESCE(SUM(vat_amount),0) AS vat_amount,COALESCE(SUM(grand_total),0) AS grand_total FROM sales.sales_invoice WHERE posting_status='Posted' AND posted_at IS NOT NULL"
                )
            )
            .mappings()
            .one()
        )
        assert report["totals"]["invoice_count"] == totals["invoice_count"]
        for key in ("total_net", "vat_amount", "grand_total"):
            assert Decimal(report["totals"][key]) == totals[key]
        expected_territories = dict(
            db.execute(
                text(
                    "SELECT territory_id,SUM(grand_total) FROM sales.sales_invoice WHERE posting_status='Posted' AND posted_at IS NOT NULL GROUP BY territory_id"
                )
            ).all()
        )
        assert {
            row["territory_id"]: Decimal(row["grand_total"])
            for row in report["by_territory"]
        } == {str(k): v for k, v in expected_territories.items()}
        for day in (
            data["today"] - timedelta(days=1),
            data["today"],
            data["today"] + timedelta(days=1),
        ):
            response = client.get(
                "/reports/management-summary", params={"as_of": str(day)}
            )
            assert response.status_code == 200
            summary = response.json()
            sales = (
                db.execute(
                    text(
                        "SELECT count(*) AS n,COALESCE(SUM(grand_total),0) AS gross,COALESCE(SUM(total_net),0) AS net,COALESCE(SUM(vat_amount),0) AS vat FROM sales.sales_invoice WHERE posting_status='Posted' AND posted_at IS NOT NULL AND invoice_date BETWEEN :start AND :end"
                    ),
                    {"start": day.replace(day=1), "end": day},
                )
                .mappings()
                .one()
            )
            assert summary["sales"]["invoices_mtd"] == sales["n"]
            assert Decimal(summary["sales"]["grand_total_mtd"]) == sales["gross"]
            assert Decimal(summary["sales"]["net_mtd"]) == sales["net"]
            assert Decimal(summary["sales"]["vat_mtd"]) == sales["vat"]
            collections = db.scalar(
                text(
                    "SELECT COALESCE(SUM(amount),0) FROM finance.payment_receipt WHERE status='Active' AND receipt_date BETWEEN :start AND :end"
                ),
                {"start": day.replace(day=1), "end": day},
            )
            assert Decimal(summary["collections"]["amount_mtd"]) == collections
            balances = db.execute(
                text(
                    "SELECT customer_id,SUM(debit-credit) FROM finance.ar_entry WHERE entry_date<=:day GROUP BY customer_id"
                ),
                {"day": day},
            ).all()
            assert Decimal(summary["receivables"]["outstanding_total"]) == sum(
                (row[1] for row in balances), Decimal(0)
            )
            assert summary["receivables"]["customers_with_balance"] == sum(
                row[1] != 0 for row in balances
            )
        response = client.get(
            "/inventory/cover", params={"warehouse_id": str(data["warehouse"])}
        )
        assert response.status_code == 200
        cover = {row["product_id"]: row for row in response.json()}
        for key in ("product", "nohistory"):
            row = cover[str(data[key])]
            stock = db.scalar(
                text(
                    "SELECT SUM(quantity) FROM inventory.stock_balance WHERE warehouse_id=:w AND product_id=:p"
                ),
                {"w": data["warehouse"], "p": data[key]},
            )
            assert Decimal(row["on_hand"]) == stock
            sold = db.scalar(
                text(
                    "SELECT SUM(l.quantity) FROM sales.sales_invoice_line l JOIN sales.sales_invoice i ON i.id=l.invoice_id WHERE i.warehouse_id=:w AND l.product_id=:p AND i.posting_status='Posted' AND i.invoice_date BETWEEN CURRENT_DATE-:days AND CURRENT_DATE"
                ),
                {"w": data["warehouse"], "p": data[key], "days": row["window_days"]},
            )
            if sold is None:
                assert (
                    row["status"] == "no_sales_history"
                    and row["cover_days"] is None
                    and row["avg_daily_sales"] is None
                )
            else:
                assert Decimal(row["sold_in_window"]) == sold
                expected_cover = stock / (sold / Decimal(row["window_days"]))
                assert Decimal(row["cover_days"]) == expected_cover
                assert row["status"] == (
                    "overstock" if expected_cover > row["threshold_days"] else "ok"
                )
        assert (
            db.scalar(
                text(
                    "SELECT count(*) FROM inventory.stock_movement WHERE source_id=:id"
                ),
                {"id": data["draft"]},
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM finance.ar_entry WHERE invoice_id=:id"),
                {"id": data["draft"]},
            )
            == 0
        )
        assert db.scalar(
            text(
                "SELECT quantity FROM inventory.stock_balance WHERE warehouse_id=:w AND product_id=:p AND batch_id=:b"
            ),
            {"w": data["warehouse"], "p": data["product"], "b": data["batch"]},
        ) == Decimal(998)


@pytest.mark.parametrize("delivery", ["success", "error"])
def test_i1_old_warehouse_labels_do_not_repopulate_new_account(
    live_app, i1_dataset, delivery
):
    from app.auth.repo import create_user

    reader = "i1_warehouse_reader_" + uuid4().hex[:8]
    password = "Synthetic-I1-Reader-2026!"
    with Session(live_app[1]) as db:
        create_user(db, reader, password, role="sales_manager", is_owner=False)
        db.commit()
    with _browser_user(live_app) as (page, _engine, _user):
        old = page.evaluate("localStorage.getItem('token')")
        held = []

        def intercept(route):
            if (
                route.request.headers.get("authorization") == "Bearer " + old
                and not held
            ):
                held.append(route)
            else:
                route.continue_()

        page.route("**/master/warehouses*", intercept)
        page.add_init_script("""(() => {
            const token = localStorage.getItem('token');
            const original = window.fetch;
            window.fetch = async (...args) => {
                const response = await original(...args);
                if (response.headers.get('x-i1-held') === 'true' && args[1].headers.Authorization === 'Bearer ' + token) {
                    const read = response.text.bind(response);
                    response.text = async () => { const body = await read(); window.__i1WarehouseRead = true; return body; };
                }
                return response;
            };
        })();""")
        with page.expect_request(lambda r: "/master/warehouses" in r.url):
            page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        wait_for_held(page, held)
        assert len(held) == 1
        prior = held[0].fetch()
        assert prior.status == 200 and any(
            r["id"] == str(i1_dataset["warehouse"]) for r in prior.json()
        )
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        page.locator("#login-username").fill(reader)
        page.locator("#login-password").fill(password)
        page.locator("#login-submit").click()
        expect(page.locator("#home-view")).to_be_visible()
        token = page.evaluate("localStorage.getItem('token')")
        assert (
            page.request.get(
                live_app[0] + "/master/warehouses",
                headers={"Authorization": "Bearer " + token},
            ).json()
            == []
        )
        if delivery == "success":
            held[0].fulfill(
                response=prior, headers={**prior.headers, "x-i1-held": "true"}
            )
        else:
            held[0].fulfill(
                status=401,
                headers={"x-i1-held": "true"},
                content_type="application/json",
                body='{"detail":"Old warehouse request"}',
            )
        page.wait_for_function("window.__i1WarehouseRead === true")
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
        assert page.evaluate("localStorage.getItem('token')") == token
        expect(
            page.locator(f'#warehouse option[value="{i1_dataset["warehouse"]}"]')
        ).to_have_count(0)


REPORTS = {
    "salesreport": ("/invoices/report", "#sr-totals-rows", "#salesreport-error"),
    "inventoryalerts": ("/inventory/cover", "#invalerts-rows", "#invalerts-error"),
    "mgmtsummary": (
        "/reports/management-summary",
        "#mgmtsummary-rows",
        "#mgmtsummary-error",
    ),
}


@pytest.mark.parametrize("view", REPORTS)
def test_i1_report_logout_erases_cached_figures(live_app, i1_dataset, view):
    with _browser_user(live_app) as (page, _engine, _owner):
        path, rows, _error = REPORTS[view]
        with page.expect_response(
            lambda r: path in r.url and r.request.method == "GET"
        ) as response:
            nav(page, view)
        assert response.value.status == 200
        expect(page.locator(rows + " tr")).not_to_have_count(0)
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        expect(page.locator(rows)).to_have_text("")
        if view == "mgmtsummary":
            expect(page.locator("#ms-kpi-sales")).to_have_text("—")
            expect(page.locator("#mgmtsummary-asof")).to_have_text("")


@pytest.mark.parametrize("view", REPORTS)
@pytest.mark.parametrize("delivery", ["success", "error"])
def test_i1_late_report_cannot_cross_accounts(live_app, i1_dataset, view, delivery):
    from app.auth.repo import create_user

    username = "i1_reader_" + uuid4().hex[:10]
    password = "Synthetic-I1-Reader-2026!"
    with Session(live_app[1]) as db:
        create_user(db, username, password, role="sales_manager", is_owner=False)
        db.commit()
    path, rows, error = REPORTS[view]
    with _browser_user(live_app) as (page, _engine, _owner):
        nav(page, view)
        expect(page.locator(rows + " tr")).not_to_have_count(0)
        old = page.evaluate("localStorage.getItem('token')")
        page.evaluate(
            """([path, token]) => {
            const original = window.fetch;
            window.__i1Consumed = false;
            window.fetch = async (...args) => {
                const response = await original(...args);
                if (String(args[0]).startsWith(path) && args[1].headers.Authorization === 'Bearer ' + token) {
                    const read = response.text.bind(response);
                    response.text = async () => { const body = await read(); window.__i1Consumed = true; return body; };
                }
                return response;
            };
        }""",
            [path, old],
        )
        held = []
        page.route("**" + path + "*", lambda route: held.append(route))
        expect(page.locator(f'[data-refresh="{view}"]')).to_be_enabled()
        with page.expect_request(lambda r: path in r.url):
            page.locator(f'[data-refresh="{view}"]').click()
        wait_for_held(page, held)
        assert held, "An old-account report request must actually be held"
        prior = held[0].fetch()
        assert prior.status == 200
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        page.locator("#login-username").fill(username)
        page.locator("#login-password").fill(password)
        expect(page.locator("#login-submit")).to_be_enabled()
        page.locator("#login-submit").click()
        expect(page.locator("#home-view")).to_be_visible()
        current = page.evaluate("localStorage.getItem('token')")
        scoped = page.request.get(
            live_app[0] + path, headers={"Authorization": "Bearer " + current}
        )
        value = scoped.json()
        if view == "inventoryalerts":
            assert (
                scoped.status == 403
            )  # No assigned warehouse is not an empty authorized warehouse.
        elif view == "salesreport":
            assert scoped.status == 200
            assert value["totals"]["invoice_count"] == 0
        else:
            assert scoped.status == 200
            assert value["sales"]["invoices_mtd"] == 0
        if delivery == "success":
            held[0].fulfill(response=prior)
        else:
            held[0].fulfill(
                status=401,
                content_type="application/json",
                body=json.dumps({"detail": "I1 old-account error"}),
            )
        page.wait_for_function("window.__i1Consumed === true")
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
        assert page.evaluate("localStorage.getItem('token')") == current
        expect(page.locator(rows)).to_have_text("")
        expect(page.locator(error)).not_to_contain_text("I1 old-account error")
        page.unroute("**" + path + "*")


def capture_i1(page, request, view, lang, width, observed):
    from pathlib import Path

    out = Path(request.config.option.xmlpath).parent / "i1-browser"
    out.mkdir(exist_ok=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("html").get_attribute("lang") == lang
    assert page.locator("html").get_attribute("dir") == (
        "rtl" if lang == "ar" else "ltr"
    )
    name = f"{view}-{lang}-{width}"
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(out / (name + ".png")), full_page=False)
    (out / (name + ".json")).write_text(
        json.dumps(
            {
                "view": view,
                "lang": lang,
                "dir": page.locator("html").get_attribute("dir"),
                "width": width,
                "observed": observed,
                "reduced_motion": page.evaluate(
                    "matchMedia('(prefers-reduced-motion: reduce)').matches"
                ),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "lang,label", [("ar", "حتى تاريخ"), ("en", "As of date")], ids=["ar", "en"]
)
def test_i1_management_summary_date_label_describes_as_of(live_app, lang, label):
    with _browser_user(live_app, lang=lang, width=390) as (page, _engine, _owner):
        nav(page, "mgmtsummary", 390)
        expect(page.locator('label[for="ms-date"]')).to_have_text(label)
        expect(page.get_by_label(label, exact=True)).to_have_attribute("id", "ms-date")


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1440])
def test_i1_complete_employee_journey(live_app, i1_dataset, lang, width, request):
    from test_customer_pwa import fill_customer

    data = i1_dataset
    with _browser_user(live_app, lang=lang, width=width) as (page, engine, owner):
        page.emulate_media(reduced_motion="reduce")
        nav(page, "customers", width)
        page.locator("#customer-add").click()
        expect(page.locator("#customer-save")).to_be_enabled()
        code = "I1-UI-" + uuid4().hex[:12]
        fill_customer(page, str(data["branch"]), str(data["territory"]), code)
        page.locator("#customer-phone").fill("٠١٠ ٩٨٧٦-٥٤٣٢")
        page.locator("#customer-address").fill("١٢ شارع النيل - القاهرة")
        with page.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith("/master/customers")
        ) as created:
            page.locator("#customer-save").click()
        assert created.value.status == 201, created.value.text()
        cid = created.value.json()["id"]
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        row = page.locator(f'tr[data-customer-id="{cid}"]')
        expect(row).to_contain_text(code)
        row.locator("[data-customer-edit]").click()
        expect(page.locator("#customer-phone")).to_have_value("٠١٠ ٩٨٧٦-٥٤٣٢")
        page.locator("#customer-name-ar").fill("عميل التكامل المعدل")
        page.locator("#customer-phone").fill("010 1234-5678")
        with page.expect_response(
            lambda r: (
                r.request.method == "PATCH"
                and r.url.endswith("/master/customers/" + cid)
            )
        ) as edited:
            page.locator("#customer-save").click()
        assert edited.value.status == 200
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        expect(row).to_contain_text("010 1234-5678")
        page.once("dialog", lambda dialog: dialog.accept())
        row.locator("[data-customer-deactivate]").click()
        expect(row.locator("[data-customer-reactivate]")).to_be_visible()
        expect(page.locator(f'#customer option[value="{cid}"]')).to_have_count(0)
        page.once("dialog", lambda dialog: dialog.accept())
        row.locator("[data-customer-reactivate]").click()
        expect(row.locator("[data-customer-deactivate]")).to_be_visible()
        expect(page.locator(f'#customer option[value="{cid}"]')).to_have_count(1)
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        nav(page, "customers", width)
        expect(row).to_contain_text("010 1234-5678")
        row.locator("[data-customer-edit]").click()
        page.keyboard.press("Escape")
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        with engine.connect() as witness:
            stored = (
                witness.execute(
                    text(
                        "SELECT name_ar,contact_phone,address,is_active FROM master_data.master_customer WHERE id=:id"
                    ),
                    {"id": cid},
                )
                .mappings()
                .one()
            )
            assert dict(stored) == {
                "name_ar": "عميل التكامل المعدل",
                "contact_phone": "010 1234-5678",
                "address": "١٢ شارع النيل - القاهرة",
                "is_active": True,
            }
            actors = (
                witness.execute(
                    text(
                        "SELECT actor_user_id FROM audit.audit_log WHERE entity_type='master_customer' AND entity_id=:id"
                    ),
                    {"id": cid},
                )
                .scalars()
                .all()
            )
            assert len(actors) == 4 and set(actors) == {owner}
        capture_i1(
            page,
            request,
            "customers",
            lang,
            width,
            {"created_edited_reactivated": True, "contacts_persisted": True},
        )
        nav(page, "suppliers", width)
        page.locator("#supplier-add").click()
        expect(page.locator("#supplier-dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#supplier-dialog")).not_to_be_visible()
        expect(page.locator("#suppliers-view")).to_be_visible()
        nav(page, "salesreport", width)
        token = page.evaluate("localStorage.getItem('token')")
        auth = {"Authorization": "Bearer " + token}
        report = page.request.get(live_app[0] + "/invoices/report", headers=auth).json()
        expect(page.locator("#sr-totals-rows td").nth(3)).to_have_text(
            report["totals"]["grand_total"]
        )
        expect(page.locator("#sr-rep-rows")).to_contain_text(data["prefix"])
        capture_i1(page, request, "salesreport", lang, width, report["totals"])
        page.locator("#sr-from").fill(str(data["today"] + timedelta(days=2)))
        page.locator('[data-refresh="salesreport"]').click()
        expect(page.locator("#sr-totals-rows td").first).to_have_text("0")
        page.locator("#sr-from").fill("")
        page.locator('[data-refresh="salesreport"]').click()
        expect(page.locator("#sr-totals-rows td").nth(3)).to_have_text(
            report["totals"]["grand_total"]
        )
        nav(page, "inventoryalerts", width)
        page.locator("#invalerts-search").fill(data["prefix"])
        expect(page.locator("#invalerts-rows tr")).to_have_count(1)
        expect(page.locator("#invalerts-rows")).to_contain_text("998")
        page.locator("#invalerts-status").select_option("no_sales_history")
        expect(page.locator("#invalerts-rows")).to_contain_text(
            data["prefix"] + "nohistory"
        )
        page.locator("#invalerts-status").select_option("all")
        page.locator("#invalerts-sort").select_option("onhand_desc")
        expect(page.locator("#invalerts-rows tr")).to_have_count(2)
        expect(
            page.locator("#invalerts-rows tr").first.locator("td").nth(2)
        ).to_have_text("998")
        page.locator("#invalerts-search").fill("I1-NOTHING-MATCHES")
        expect(page.locator("#invalerts-rows td")).to_have_count(1)
        page.locator("#invalerts-search").fill(data["prefix"])
        expect(page.locator("#invalerts-rows tr")).to_have_count(2)
        capture_i1(
            page,
            request,
            "inventoryalerts",
            lang,
            width,
            {"overstock": 998, "no_history": 17, "searched_sorted": True},
        )
        nav(page, "mgmtsummary", width)
        day = data["today"] + timedelta(days=1)
        page.locator("#ms-date").fill(str(day))
        expected = page.request.get(
            live_app[0] + "/reports/management-summary?as_of=" + str(day), headers=auth
        ).json()
        expect(page.locator("#ms-kpi-collections")).to_have_text(
            expected["collections"]["amount_mtd"]
        )
        expect(page.locator("#ms-kpi-ar")).to_have_text(
            expected["receivables"]["outstanding_total"]
        )
        page.locator('[data-refresh="mgmtsummary"]').focus()
        page.keyboard.press("Enter")
        expect(page.locator("#mgmtsummary-asof")).to_contain_text(str(day))
        expect(page.locator("#ms-kpi-sales")).to_have_text(
            expected["sales"]["grand_total_mtd"]
        )
        assert (
            page.locator("#ms-kpis").evaluate("e => getComputedStyle(e).animationName")
            == "none"
        )
        capture_i1(page, request, "mgmtsummary", lang, width, expected)
        observed_routes = []

        def fail_route(route):
            observed_routes.append(route)
            return route.fulfill(
                status=503,
                content_type="application/json",
                body='{"detail":"I1 temporary report outage"}',
            )

        page.route("**/reports/management-summary*", fail_route)
        page.locator('[data-refresh="mgmtsummary"]').click()
        expect(page.locator("#mgmtsummary-error")).to_contain_text(
            "I1 temporary report outage"
        )
        expect(page.locator("#ms-kpi-sales")).to_have_text("—")
        wait_for_held(page, observed_routes)
        page.unroute("**/reports/management-summary*")
        page.locator('[data-refresh="mgmtsummary"]').click()
        expect(page.locator("#ms-kpi-sales")).to_have_text(
            expected["sales"]["grand_total_mtd"]
        )
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        expect(page.locator("#customer-rows")).to_have_text("")


@pytest.mark.parametrize(
    "role", ["finance", "sales_manager", "medical_rep", "warehouse_staff"]
)
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_i1_role_boundaries_in_browser_and_http(live_app, i1_dataset, role, lang):
    data = i1_dataset
    with _browser_user(live_app, role=role, owner=False, lang=lang, width=390) as (
        page,
        engine,
        user,
    ):
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t)"
                ),
                {"u": user, "t": data["territory"]},
            )
            db.execute(
                text(
                    "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b)"
                ),
                {"u": user, "b": data["branch"]},
            )
        auth = {
            "Authorization": "Bearer " + page.evaluate("localStorage.getItem('token')")
        }
        expected = {
            "salesreport": role != "warehouse_staff",
            "inventoryalerts": role != "medical_rep",
            "mgmtsummary": role not in {"medical_rep", "warehouse_staff"},
        }
        for view, allowed in expected.items():
            path, _rows, _error = REPORTS[view]
            response = page.request.get(live_app[0] + path, headers=auth)
            assert response.status == (200 if allowed else 403), (
                role,
                view,
                response.text(),
            )
            if allowed:
                nav(page, view, 390)
                expect(page.locator(f"#{view}-view")).to_be_visible()
                if view == "salesreport" and role == "medical_rep":
                    assert response.json()["totals"]["invoice_count"] == 0
            else:
                expect(page.locator(f'#sidebar [data-view="{view}"]')).to_be_hidden()
        nav(page, "customers", 390)
        expect(page.locator("#customer-add")).to_be_hidden()
        assert (
            page.request.patch(
                live_app[0] + "/master/customers/" + str(data["customer"]),
                headers=auth,
                data={"contact_phone": "forbidden"},
            ).status
            == 403
        )
