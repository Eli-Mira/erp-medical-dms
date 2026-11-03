"""Real customer PWA -> API -> independently committed PostgreSQL rows."""

from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from browser_readiness import wait_for_held
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_supplier_pwa import (
    live_app as live_app,  # noqa: PLC0414 - pytest fixture re-export
)


@contextmanager
def _browser_user(live_app, role="owner", owner=True, lang="ar", width=1440):
    from app.auth.repo import create_user

    base, engine = live_app
    username = "customer_ui_" + uuid4().hex[:12]
    password = "Synthetic-Customer-Test-2026!"
    with Session(engine) as db:
        create_user(db, username, password, role=role, is_owner=owner)
        db.commit()
        user_id = db.scalar(
            text("SELECT id FROM platform.platform_user WHERE username=:u"),
            {"u": username},
        )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with browser.new_context(
                service_workers="block", viewport={"width": width, "height": 900}
            ) as context:
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/app/", wait_until="domcontentloaded")
                page.locator("#login-username").fill(username)
                page.locator("#login-password").fill(password)
                page.locator("#login-submit").click()
                expect(page.locator("#home-view")).to_be_visible()
                if lang == "en":
                    page.locator("#lang").click()
                expect(page.locator("html")).to_have_attribute("lang", lang)
                expect(page.locator("html")).to_have_attribute(
                    "dir", "rtl" if lang == "ar" else "ltr"
                )
                yield page, engine, user_id
                assert errors == []
        finally:
            browser.close()


def customer_page(page, width):
    if (
        width < 1024
        and page.locator("#menu-toggle").get_attribute("aria-expanded") != "true"
    ):
        page.locator("#menu-toggle").click()
    page.locator('#sidebar [data-view="customers"]').click()
    expect(page.locator("#customers-view")).to_be_visible()


def references(engine):
    branch, territory = uuid4(), uuid4()
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO master_data.master_branch(id,code,name_ar,name_en) VALUES (:id,:code,'فرع المتصفح','Browser branch')"
            ),
            {"id": branch, "code": branch.hex[:20]},
        )
        db.execute(
            text(
                "INSERT INTO master_data.master_territory(id,code,name_ar,name_en) VALUES (:id,:code,'منطقة المتصفح','Browser territory')"
            ),
            {"id": territory, "code": territory.hex[:20]},
        )
    return str(branch), str(territory)


def fill_customer(page, branch, territory, code):
    page.locator("#customer-code").fill(code)
    page.locator("#customer-name-ar").fill("عميل اختبار المتصفح")
    page.locator("#customer-name-en").fill("Browser customer")
    page.locator("#customer-branch").select_option(branch)
    page.locator("#customer-territory").select_option(territory)


def capture(page, request, state):
    target = Path(request.config.option.xmlpath).parent / "screenshots"
    target.mkdir(exist_ok=True)
    page.screenshot(
        path=str(target / (request.node.name + "-" + state + ".png")), full_page=False
    )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if page.locator("#customer-dialog").is_visible():
        assert page.locator("#customer-dialog").evaluate(
            "e => {const r=e.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth && r.height<=innerHeight;}"
        )


def test_deactivation_invalidates_invoice_choice_when_refresh_fails(live_app):
    branch, territory = references(live_app[1])
    with _browser_user(live_app) as (page, _engine, _owner):
        customer_page(page, 1440)
        page.locator("#customer-add").click()
        fill_customer(page, branch, territory, "REFRESH-" + uuid4().hex[:12])
        with page.expect_response(
            lambda r: r.url.endswith("/master/customers") and r.request.method == "POST"
        ) as created:
            page.locator("#customer-save").click()
        assert created.value.status == 201
        cid = created.value.json()["id"]
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        option = page.locator(f'#customer option[value="{cid}"]')
        expect(option).to_have_count(1)
        row = page.locator(f'tr[data-customer-id="{cid}"]')
        observed_routes = []

        def fail_route(route):
            if route.request.method == "GET":
                observed_routes.append(route)
                return route.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"detail":"Synthetic refresh failure"}',
                )
            return route.continue_()

        page.route("**/master/customers*", fail_route)
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + cid)
                and r.request.method == "DELETE"
            )
        ) as changed:
            row.locator("[data-customer-deactivate]").click()
        assert changed.value.status == 204
        expect(page.locator("#customers-error")).to_contain_text(
            "Synthetic refresh failure"
        )
        expect(option).to_have_count(0)
        wait_for_held(page, observed_routes)
        page.unroute("**/master/customers*")
        page.locator('[data-refresh="customers"]').click()
        expect(page.locator("#customers-error")).not_to_be_visible()
        expect(row.locator("[data-customer-reactivate]")).to_be_visible()
        expect(option).to_have_count(0)
        page.once("dialog", lambda dialog: dialog.accept())
        row.locator("[data-customer-reactivate]").click()
        expect(option).to_have_count(1)


@pytest.mark.parametrize("role", ["finance", "medical_rep", "read_only_auditor"])
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_customer_readers_have_no_mutation_controls(live_app, role, lang):
    branch, territory = references(live_app[1])
    with _browser_user(live_app, role=role, owner=False, lang=lang, width=390) as (
        page,
        engine,
        user,
    ):
        cid = uuid4()
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,'عميل للقراءة',:b,:t)"
                ),
                {"id": cid, "code": cid.hex[:30], "b": branch, "t": territory},
            )
            db.execute(
                text(
                    "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t)"
                ),
                {"u": user, "t": territory},
            )
        customer_page(page, 390)
        expect(page.locator(f'tr[data-customer-id="{cid}"]')).to_be_visible()
        expect(page.locator("#customer-add")).not_to_be_visible()
        expect(
            page.locator(
                "[data-customer-edit], [data-customer-deactivate], [data-customer-reactivate]"
            )
        ).to_have_count(0)


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_customer_duplicate_cancel_and_single_flight(live_app, lang):
    branch, territory = references(live_app[1])
    with _browser_user(live_app, lang=lang, width=390) as (page, engine, _user):
        duplicate = "DUP-" + uuid4().hex[:12]
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO master_data.master_customer(code,name_ar,branch_id,territory_id) VALUES (:code,'عميل موجود',:b,:t)"
                ),
                {"code": duplicate, "b": branch, "t": territory},
            )
        customer_page(page, 390)
        page.locator("#customer-add").click()
        fill_customer(page, branch, territory, duplicate)
        with page.expect_response(
            lambda r: r.url.endswith("/master/customers") and r.request.method == "POST"
        ) as conflict:
            page.locator("#customer-save").click()
        assert conflict.value.status == 409
        expect(page.locator("#customer-dialog-error")).to_contain_text(
            "كود العميل مسجل بالفعل" if lang == "ar" else "already exists"
        )
        expect(page.locator("#customer-code")).to_have_value(duplicate)
        page.keyboard.press("Escape")
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        page.locator("#customer-add").click()
        code = "SINGLE-" + uuid4().hex[:12]
        fill_customer(page, branch, territory, code)
        held = []
        page.route(
            "**/master/customers",
            lambda route: (
                held.append(route)
                if route.request.method == "POST"
                else route.continue_()
            ),
        )
        with page.expect_request(
            lambda r: r.url.endswith("/master/customers") and r.method == "POST"
        ):
            page.locator("#customer-save").click()
        expect(page.locator("#customer-save")).to_be_disabled()
        expect(page.locator("#customer-cancel")).to_be_disabled()
        page.locator("#customer-form").evaluate(
            "f => f.dispatchEvent(new Event('submit', {cancelable:true}))"
        )
        page.keyboard.press("Escape")
        expect(page.locator("#customer-dialog")).to_be_visible()
        wait_for_held(page, held)
        assert len(held) == 1
        with page.expect_response(
            lambda r: r.url.endswith("/master/customers") and r.request.method == "POST"
        ) as created:
            held[0].continue_()
        assert created.value.status == 201
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        with engine.connect() as db:
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM master_data.master_customer WHERE code=:code"
                    ),
                    {"code": duplicate},
                )
                == 1
            )
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM audit.audit_log WHERE entity_type='master_customer' AND new_values->>'code'=:code"
                    ),
                    {"code": code},
                )
                == 1
            )


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_customer_reference_failure_is_recoverable_without_write(live_app, lang):
    branch, territory = references(live_app[1])
    with _browser_user(live_app, lang=lang) as (page, engine, _user):
        customer_page(page, 1440)
        expect(page.locator("#customer-add")).to_be_visible()
        observed_routes = []

        def fail_route(route):
            observed_routes.append(route)
            return route.fulfill(
                status=503,
                content_type="application/json",
                body='{"detail":"Synthetic unavailable reference"}',
            )

        page.route("**/master/territories", fail_route)
        page.locator("#customer-add").click()
        expect(page.locator("#customer-dialog-error")).to_be_visible()
        expect(page.locator("#customer-save")).to_be_disabled()
        page.locator("#customer-cancel").click()
        wait_for_held(page, observed_routes)
        page.unroute("**/master/territories")
        page.locator("#customer-add").click()
        fill_customer(page, branch, territory, "CANCEL-" + uuid4().hex[:12])
        code = page.locator("#customer-code").input_value()
        page.locator("#customer-cancel").click()
        with engine.connect() as db:
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM master_data.master_customer WHERE code=:code"
                    ),
                    {"code": code},
                )
                == 0
            )


@pytest.mark.parametrize(
    "lang,width", [("ar", 1440), ("en", 1440), ("ar", 390), ("en", 390)]
)
def test_owner_customer_workflow_persists_after_refresh(live_app, lang, width, request):
    branch, territory = references(live_app[1])
    with _browser_user(live_app, lang=lang, width=width) as (page, engine, owner):
        customer_page(page, width)
        expect(page.locator("#customer-add")).to_have_text(
            "إضافة عميل" if lang == "ar" else "Add customer"
        )
        page.locator("#customer-add").click()
        expect(page.locator("#customer-dialog")).to_be_visible()
        page.locator("#customer-save").click()
        assert page.locator("#customer-code").evaluate("e => e.validity.valueMissing")
        expect(page.locator("#customer-dialog")).to_be_visible()
        code = "UI-" + uuid4().hex[:16]
        fill_customer(page, branch, territory, code)
        capture(page, request, "create")
        with page.expect_response(
            lambda r: r.url.endswith("/master/customers") and r.request.method == "POST"
        ) as created:
            page.locator("#customer-save").click()
        assert created.value.status == 201, created.value.text()
        body = created.value.json()
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        row = page.locator(f'tr[data-customer-id="{body["id"]}"]')
        expect(row).to_contain_text(code)
        row.locator("[data-customer-edit]").click()
        expect(page.locator("#customer-dialog")).to_be_visible()
        expect(page.locator("#customer-code")).to_be_disabled()
        expect(page.locator("#customer-branch")).to_be_disabled()
        page.locator("#customer-name-ar").fill("عميل معدل")
        page.locator("#customer-name-en").fill("")
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + body["id"])
                and r.request.method == "PATCH"
            )
        ) as changed:
            page.locator("#customer-save").click()
        assert changed.value.status == 200, changed.value.text()
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        expect(row).to_contain_text("عميل معدل")
        page.once("dialog", lambda d: d.accept())
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + body["id"])
                and r.request.method == "DELETE"
            )
        ) as deactivated:
            row.locator("[data-customer-deactivate]").click()
        assert deactivated.value.status == 204
        expect(row.locator("[data-customer-reactivate]")).to_be_visible()
        assert page.locator(f'#customer option[value="{body["id"]}"]').count() == 0
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        customer_page(page, width)
        expect(row.locator("[data-customer-reactivate]")).to_be_visible()
        row.scroll_into_view_if_needed()
        capture(page, request, "inactive")
        page.once("dialog", lambda d: d.accept())
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + body["id"] + "/activate")
                and r.request.method == "PATCH"
            )
        ) as reactivated:
            row.locator("[data-customer-reactivate]").click()
        assert reactivated.value.status == 200
        expect(row.locator("[data-customer-deactivate]")).to_be_visible()
        expect(page.locator(f'#customer option[value="{body["id"]}"]')).to_have_count(1)
        row.locator("[data-customer-edit]").click()
        expect(page.locator("#customer-dialog")).to_be_visible()
        page.locator("#customer-save").click()
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        with engine.connect() as db:
            stored = (
                db.execute(
                    text(
                        "SELECT name_ar,name_en,is_active,branch_id,territory_id FROM master_data.master_customer WHERE id=:id"
                    ),
                    {"id": body["id"]},
                )
                .mappings()
                .one()
            )
            assert (
                stored["name_ar"] == "عميل معدل"
                and stored["name_en"] is None
                and stored["is_active"] is True
            )
            assert (
                str(stored["branch_id"]) == branch
                and str(stored["territory_id"]) == territory
            )
            audits = (
                db.execute(
                    text(
                        "SELECT actor_user_id,action FROM audit.audit_log WHERE entity_type='master_customer' AND entity_id=:id"
                    ),
                    {"id": body["id"]},
                )
                .mappings()
                .all()
            )
            assert sorted(a["action"] for a in audits) == [
                "activated",
                "created",
                "deactivated",
                "updated",
            ]
            assert all(a["actor_user_id"] == owner for a in audits)
        for key, view in [
            ("home", "home-view"),
            ("invoice", "invoice-view"),
            ("inventory", "inventory-view"),
        ]:
            if width < 1024:
                page.locator("#menu-toggle").click()
            page.locator(f'#sidebar [data-view="{key}"]').first.click()
            expect(page.locator("#" + view)).to_be_visible()
