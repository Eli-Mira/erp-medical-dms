"""Stock-visit UI states, scoped server data, and actual browser session races."""

import hashlib
import json
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from browser_readiness import wait_for_held
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_customer_pwa import _browser_user, capture, references
from test_pwa_stock_visits import visits_page
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


@contextmanager
def visit_user(live_app, lang="en", width=390, role="owner"):
    base, _engine = live_app
    with _browser_user(
        live_app, role=role, owner=role == "owner", lang=lang, width=width
    ) as (page, engine, actor):
        branch, territory = references(engine)
        ids = {name: uuid4() for name in ("customer", "product", "warehouse", "batch")}
        ids.update(branch=branch, territory=territory)
        try:
            with engine.begin() as db:
                db.execute(
                    text(
                        "INSERT INTO master_data.master_customer(id,code,name_ar,name_en,branch_id,territory_id) VALUES (:id,:code,'عميل متابعة المتصفح','Browser field customer',:b,:t)"
                    ),
                    {
                        "id": ids["customer"],
                        "code": ids["customer"].hex[:30],
                        "b": branch,
                        "t": territory,
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO master_data.master_product(id,sku,name_ar,name_en,base_price,vat_rate) VALUES (:id,:sku,'صنف متابعة المتصفح','Browser field product',0,0)"
                    ),
                    {"id": ids["product"], "sku": ids["product"].hex},
                )
                db.execute(
                    text(
                        "INSERT INTO master_data.master_warehouse(id,code,name_ar,branch_id) VALUES (:id,:code,'S8 synthetic warehouse',:branch)"
                    ),
                    {
                        "id": ids["warehouse"],
                        "code": ids["warehouse"].hex[:20],
                        "branch": branch,
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date) VALUES (:id,:p,:w,'S8-SYNTHETIC',:ed)"
                    ),
                    {
                        "id": ids["batch"],
                        "p": ids["product"],
                        "w": ids["warehouse"],
                        "ed": date(2030, 1, 1),
                    },
                )
                db.execute(
                    text(
                        "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t) ON CONFLICT DO NOTHING"
                    ),
                    {"u": actor, "t": territory},
                )
                db.execute(
                    text(
                        "INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b) ON CONFLICT DO NOTHING"
                    ),
                    {"u": actor, "b": branch},
                )
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#home-view")).to_be_visible()
            yield page, engine, actor, ids, base
        finally:
            with engine.begin() as db:
                db.execute(
                    text("DELETE FROM sales.customer_held_stock WHERE customer_id=:id"),
                    {"id": ids["customer"]},
                )
                db.execute(
                    text(
                        "DELETE FROM sales.customer_stock_visit WHERE customer_id=:id"
                    ),
                    {"id": ids["customer"]},
                )
                db.execute(
                    text("DELETE FROM inventory.batch_record WHERE id=:id"),
                    {"id": ids["batch"]},
                )
                db.execute(
                    text("DELETE FROM master_data.master_warehouse WHERE id=:id"),
                    {"id": ids["warehouse"]},
                )
                db.execute(
                    text("DELETE FROM master_data.master_customer WHERE id=:id"),
                    {"id": ids["customer"]},
                )
                db.execute(
                    text("DELETE FROM master_data.master_product WHERE id=:id"),
                    {"id": ids["product"]},
                )
                db.execute(
                    text(
                        "DELETE FROM platform.user_territory WHERE user_id=:u AND territory_id=:t"
                    ),
                    {"u": actor, "t": territory},
                )
                db.execute(
                    text(
                        "DELETE FROM platform.user_branch WHERE user_id=:u AND branch_id=:b"
                    ),
                    {"u": actor, "b": branch},
                )
                db.execute(
                    text("DELETE FROM master_data.master_branch WHERE id=:id"),
                    {"id": branch},
                )
                db.execute(
                    text("DELETE FROM master_data.master_territory WHERE id=:id"),
                    {"id": territory},
                )


def fill_visit(page, ids):
    page.locator("#visit-customer").select_option(str(ids["customer"]))
    page.locator("#visit-product").select_option(str(ids["product"]))
    page.locator("#visit-date").fill("2026-10-15")
    for field, value in (
        ("prev", "10.125"),
        ("del", "5.250"),
        ("ret", "1.125"),
        ("cur", "8.125"),
    ):
        page.locator("#visit-" + field).fill(value)
    page.locator("#visit-amount").fill("25.50")
    page.locator("#visit-notes").fill("S8 private field note")
    expect(page.locator("#visit-st")).to_have_text("6.125")


def seeded_visit(page, base, ids, *, batch=False, current="8.125", day=14):
    token = page.evaluate("localStorage.getItem('token')")
    payload = {
        "customer_id": str(ids["customer"]),
        "visit_date": date(2026, 10, day).isoformat(),
        "lines": [
            {
                "product_id": str(ids["product"]),
                "batch_id": str(ids["batch"]) if batch else None,
                "quantity_prev": "100",
                "quantity_current": current,
            }
        ],
    }
    response = page.context.request.post(
        base + "/visits", headers={"Authorization": "Bearer " + token}, data=payload
    )
    assert response.status == 201, response.text()
    return response.json()


def saved(page, lang="en"):
    expect(page.locator("#visit-warn")).to_contain_text(
        "Visit saved on server." if lang == "en" else "تم حفظ الزيارة على الخادم."
    )


def capture_visit(page, request, state, lang, width):
    observed = page.evaluate(
        "({lang: document.documentElement.lang, dir: document.documentElement.dir, width: innerWidth, scrollWidth: document.documentElement.scrollWidth, networkOnline: navigator.onLine})"
    )
    assert observed["lang"] == lang and observed["dir"] == (
        "rtl" if lang == "ar" else "ltr"
    )
    assert observed["width"] == width and observed["scrollWidth"] <= width
    capture(page, request, state)
    png = (
        Path(request.config.option.xmlpath).parent
        / "screenshots"
        / (request.node.name + "-" + state + ".png")
    )
    png.with_suffix(".json").write_text(
        json.dumps(
            {
                **observed,
                "state": state,
                "case": request.node.name,
                "png": png.name,
                "sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1440])
def test_visit_ar_en_responsive_save_reload_delete(live_app, lang, width, request):
    with visit_user(live_app, lang, width) as (page, engine, _actor, ids, _base):
        legacy = json.dumps(
            [{"customer": "S8_LEGACY_CANARY", "sell_through": 900}], sort_keys=True
        )
        page.evaluate(
            "value => localStorage.setItem('medsys.visits.v1', value)", legacy
        )
        visits_page(page, width)
        expect(page.locator("#visit-rows")).not_to_contain_text("S8_LEGACY_CANARY")
        expect(page.locator("#visit-cur")).to_have_value("")
        fill_visit(page, ids)
        page.locator("#visit-save").click()
        saved(page, lang)
        capture_visit(page, request, "saved", lang, width)
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        visits_page(page, width)
        with engine.connect() as db:
            visit_id = db.execute(
                text("SELECT id FROM sales.customer_stock_visit WHERE customer_id=:c"),
                {"c": ids["customer"]},
            ).scalar_one()
            assert (
                db.execute(
                    text("SELECT count(*) FROM finance.ar_entry WHERE customer_id=:c"),
                    {"c": ids["customer"]},
                ).scalar_one()
                == 0
            )
        row = page.locator('#visit-rows tr[data-visit-id="' + str(visit_id) + '"]')
        expect(row).to_contain_text("6.125")
        expect(page.locator("html")).to_have_attribute("lang", lang)
        expect(page.locator("html")).to_have_attribute(
            "dir", "rtl" if lang == "ar" else "ltr"
        )
        page.once("dialog", lambda dialog: dialog.accept())
        row.get_by_role("button").click()
        expect(row).to_have_count(0)
        with engine.connect() as db:
            assert (
                db.execute(
                    text("SELECT count(*) FROM sales.customer_stock_visit WHERE id=:v"),
                    {"v": visit_id},
                ).scalar_one()
                == 0
            )
        assert page.evaluate("localStorage.getItem('medsys.visits.v1')") == legacy
        capture_visit(page, request, "deleted", lang, width)


def test_confirmed_save_prepares_next_observation(live_app):
    with visit_user(live_app) as (page, _engine, _actor, ids, _base):
        visits_page(page, 390)
        fill_visit(page, ids)
        page.locator("#visit-save").click()
        saved(page)
        expect(page.locator("#visit-warn")).to_have_attribute("role", "status")
        expect(page.locator("#visit-cur")).to_have_value("")
        expect(page.locator("#visit-amount")).to_have_value("0")
        expect(page.locator("#visit-notes")).to_have_value("")
        expect(page.locator("#visit-prev")).to_have_value("8.125")


def test_held_prefill_keeps_batched_and_unbatched_observations_separate(live_app):
    with visit_user(live_app, lang="ar", width=320) as (
        page,
        _engine,
        _actor,
        ids,
        base,
    ):
        seeded_visit(page, base, ids, batch=True, current="30")
        seeded_visit(page, base, ids, current="8.125")
        visits_page(page, 320)
        page.locator("#visit-customer").select_option(str(ids["customer"]))
        page.locator("#visit-product").select_option(str(ids["product"]))
        expect(page.locator("#visit-prev")).to_have_value("8.125")
        expect(page.locator("#visit-rows")).to_contain_text(str(ids["batch"]))
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


@pytest.mark.parametrize(
    "role", ["sales_manager", "district_manager", "read_only_auditor"]
)
def test_visit_reader_sees_history_without_write_controls(live_app, role):
    with visit_user(live_app, width=768) as (page, engine, actor, ids, base):
        row = seeded_visit(page, base, ids)
        with engine.begin() as db:
            db.execute(
                text(
                    "UPDATE platform.platform_user SET role=:r,is_owner=false WHERE id=:id"
                ),
                {"r": role, "id": actor},
            )
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        visits_page(page, 768)
        expect(
            page.locator('#visit-rows tr[data-visit-id="' + row["id"] + '"]')
        ).to_be_visible()
        expect(page.locator("#visit-save")).to_be_disabled()
        expect(page.locator("#visit-read-only")).to_be_visible()
        expect(page.locator("#visit-rows button")).to_have_count(0)


@pytest.mark.parametrize("role", ["finance", "warehouse_staff", "admin"])
def test_unpermitted_roles_have_no_visit_navigation(live_app, role):
    with visit_user(live_app, width=1440) as (page, engine, actor, _ids, base):
        with engine.begin() as db:
            db.execute(
                text(
                    "UPDATE platform.platform_user SET role=:r,is_owner=false WHERE id=:id"
                ),
                {"r": role, "id": actor},
            )
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        expect(page.locator('#sidebar [data-view="visits"]')).to_be_hidden()
        token = page.evaluate("localStorage.getItem('token')")
        assert (
            page.context.request.get(
                base + "/visits", headers={"Authorization": "Bearer " + token}
            ).status
            == 403
        )


def test_visit_rep_uses_server_bound_identity(live_app):
    with visit_user(live_app, role="medical_rep") as (page, engine, actor, ids, _base):
        visits_page(page, 390)
        fill_visit(page, ids)
        page.locator("#visit-notes").press("Enter")
        saved(page)
        with engine.connect() as db:
            assert (
                db.execute(
                    text(
                        "SELECT rep_id FROM sales.customer_stock_visit WHERE customer_id=:id"
                    ),
                    {"id": ids["customer"]},
                ).scalar_one()
                == actor
            )
        expect(page.locator("#visit-rep")).not_to_have_value("")


def test_pending_visit_single_flight_error_then_real_retry(live_app):
    with visit_user(live_app) as (page, engine, _actor, ids, _base):
        visits_page(page, 390)
        fill_visit(page, ids)
        held = []

        def hold(route):
            held.append(route)
            page.evaluate("window.__s8Held = true")

        page.route("**/visits", hold)
        try:
            page.locator("#visit-save").click()
            wait_for_held(page, held)
            expect(page.locator("#visit-save")).to_be_disabled()
            page.locator("#visit-form").evaluate(
                "form => form.dispatchEvent(new Event('submit', {bubbles:true,cancelable:true}))"
            )
            assert len(held) == 1
            held.pop().fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "S8 controlled unavailable"}),
            )
            expect(page.locator("#visit-warn")).to_contain_text(
                "S8 controlled unavailable"
            )
            expect(page.locator("#visit-save")).to_be_enabled()
            expect(page.locator("#visit-notes")).to_have_value("S8 private field note")
            with engine.connect() as db:
                assert (
                    db.execute(
                        text(
                            "SELECT count(*) FROM sales.customer_stock_visit WHERE customer_id=:c"
                        ),
                        {"c": ids["customer"]},
                    ).scalar_one()
                    == 0
                )
        finally:
            for route in held:
                route.abort()
            page.unroute("**/visits", hold)
        page.locator("#visit-save").click()
        saved(page)
        with engine.connect() as db:
            assert (
                db.execute(
                    text(
                        "SELECT count(*) FROM sales.customer_stock_visit WHERE customer_id=:c"
                    ),
                    {"c": ids["customer"]},
                ).scalar_one()
                == 1
            )


def test_visit_logout_clears_before_held_failed_transport(live_app):
    with visit_user(live_app) as (page, _engine, _actor, ids, base):
        seeded_visit(page, base, ids)
        visits_page(page, 390)
        expect(page.locator("#visit-rows [data-visit-id]")).not_to_have_count(0)
        fill_visit(page, ids)
        routes = []

        def hold(route):
            routes.append(route)

        page.route("**/auth/logout", hold)
        try:
            page.locator("#logout").click()
            expect(page.locator("#login-view")).to_be_visible()
            expect(page.locator("#visit-rows tr")).to_have_count(0)
            expect(page.locator("#visit-notes")).to_have_value("")
            expect(page.locator("#visit-prev")).to_have_value("")
            wait_for_held(page, routes)
        finally:
            for route in routes:
                route.fulfill(status=503, body="S8 controlled logout failure")
            page.unroute("**/auth/logout", hold)


@pytest.mark.parametrize("kind", ["read", "save", "old401", "stock", "stockError"])
def test_old_visit_response_cannot_repopulate_a_restricted_session(live_app, kind):
    from app.auth.repo import create_user

    with visit_user(live_app) as (page, engine, _actor, ids, base):
        row = seeded_visit(page, base, ids)
        username = "s8_restricted_" + uuid4().hex[:12]
        password = "Synthetic-S8-Restricted-2026!"
        with Session(engine) as db:
            create_user(db, username, password, role="finance", is_owner=False)
            db.commit()
        old_token = page.evaluate("localStorage.getItem('token')")
        target = "/visits/held-stock" if kind in {"stock", "stockError"} else "/visits"
        method = "POST" if kind == "save" else "GET"
        if kind in {"save", "stock", "stockError"}:
            visits_page(page, 390)
            if kind == "save":
                fill_visit(page, ids)
        page.evaluate(
            """({token, target, method}) => {
            const real = window.fetch;
            window.__s8Consumed = false;
            window.fetch = async function (url, options) {
                const response = await real.apply(this, arguments);
                if (String(url).split('?')[0] === target && (options.method || 'GET') === method && options.headers.Authorization === 'Bearer ' + token) {
                    const consume = response.text.bind(response);
                    response.text = async function () {
                        const value = await consume();
                        window.__s8Consumed = true;
                        return value;
                    };
                }
                return response;
            };
        }""",
            {"token": old_token, "target": target, "method": method},
        )
        held = []

        def hold(route):
            if (
                urlsplit(route.request.url).path == target
                and route.request.method == method
                and route.request.headers.get("authorization") == "Bearer " + old_token
            ):
                response = route.fetch()
                assert response.status in {200, 201}
                if kind not in {"stock", "stockError"}:
                    data = response.json()
                    assert (
                        data["id"]
                        if kind == "save"
                        else any(item["id"] == row["id"] for item in data["items"])
                    )
                held.append((route, response))
                page.evaluate("window.__s8OldHeld = true")
            else:
                route.continue_()

        page.route("**/visits**", hold)
        try:
            if kind in {"stock", "stockError"}:
                page.locator("#visit-customer").select_option(str(ids["customer"]))
                page.locator("#visit-product").select_option(str(ids["product"]))
            elif kind == "save":
                page.locator("#visit-save").click()
            else:
                visits_page(page, 390)
            wait_for_held(page, held)
            page.locator("#logout").click()
            expect(page.locator("#login-view")).to_be_visible()
            page.locator("#login-username").fill(username)
            page.locator("#login-password").fill(password)
            page.locator("#login-submit").click()
            expect(page.locator("#home-view")).to_be_visible()
            current = page.evaluate("localStorage.getItem('token')")
            assert current != old_token
            assert (
                page.context.request.get(
                    base + "/visits", headers={"Authorization": "Bearer " + current}
                ).status
                == 403
            )
            route, response = held.pop()
            if kind in {"old401", "stockError"}:
                route.fulfill(
                    status=401,
                    content_type="application/json",
                    body=json.dumps({"detail": "S8 old-account failure"}),
                )
            else:
                route.fulfill(response=response)
            page.wait_for_function("window.__s8Consumed === true")
            page.evaluate(
                "() => new Promise(resolve => requestAnimationFrame(() => resolve(true)))"
            )
            assert page.evaluate("localStorage.getItem('token')") == current
            expect(page.locator("#home-view")).to_be_visible()
            expect(page.locator("#visit-rows tr")).to_have_count(0)
            expect(page.locator("#visit-notes")).to_have_value("")
            expect(page.locator("#visit-prev")).to_have_value("")
            expect(page.locator("#visit-warn")).to_be_empty()
            expect(page.locator("#visit-stock-hint")).to_be_empty()
        finally:
            for route, response in held:
                route.fulfill(response=response)
            page.unroute("**/visits**", hold)


def test_expired_visit_session_clears_rows_and_form(live_app):
    with visit_user(live_app) as (page, engine, _actor, ids, base):
        row = seeded_visit(page, base, ids)
        visits_page(page, 390)
        expect(
            page.locator('#visit-rows tr[data-visit-id="' + row["id"] + '"]')
        ).to_be_visible()
        fill_visit(page, ids)
        token = page.evaluate("localStorage.getItem('token')")
        with engine.begin() as db:
            db.execute(
                text(
                    "UPDATE platform.platform_session SET expires_at=now()-interval '1 second' WHERE id=:id"
                ),
                {"id": token},
            )
        page.locator("#visits-refresh").click()
        expect(page.locator("#login-view")).to_be_visible()
        expect(page.locator("#visit-rows tr")).to_have_count(0)
        expect(page.locator("#visit-notes")).to_have_value("")
        expect(page.locator("#visit-prev")).to_have_value("")
        assert page.evaluate("localStorage.getItem('token')") is None


def test_visit_history_error_is_not_reported_as_empty_and_retry_recovers(live_app):
    with visit_user(live_app) as (page, _engine, _actor, ids, base):
        row = seeded_visit(page, base, ids)
        visits_page(page, 390)
        record = page.locator('#visit-rows tr[data-visit-id="' + row["id"] + '"]')
        expect(record).to_be_visible()

        observed_routes = []

        def unavailable(route):
            observed_routes.append(route)
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps({"detail": "S8 history unavailable"}),
            )

        page.route("**/visits?*", unavailable)
        try:
            page.locator("#visits-refresh").click()
            wait_for_held(page, observed_routes)
            expect(page.locator("#visits-error")).to_contain_text(
                "S8 history unavailable"
            )
            expect(record).to_have_count(0)
            expect(page.locator("#visit-rows")).not_to_contain_text(
                "No server visits yet."
            )
            expect(page.locator("#visits-page")).to_have_text("—")
        finally:
            page.unroute("**/visits?*", unavailable)
        page.locator("#visits-refresh").click()
        expect(record).to_be_visible()
        expect(page.locator("#visits-error")).to_be_empty()


def test_visit_history_pagination_and_last_page_delete_fallback(live_app):
    with visit_user(live_app) as (page, _engine, _actor, ids, base):
        records = [
            seeded_visit(page, base, ids, current=str(i), day=15) for i in range(23)
        ]
        visits_page(page, 390)
        expect(page.locator("#visits-page")).to_have_text("1–20 / 23")
        expect(page.locator("#visit-rows tr[data-visit-id]")).to_have_count(20)
        page.locator("#visits-next").click()
        expect(page.locator("#visits-page")).to_have_text("21–23 / 23")
        expect(page.locator("#visit-rows tr[data-visit-id]")).to_have_count(3)
        actual = page.locator("#visit-rows tr[data-visit-id]").evaluate_all(
            "rows => rows.map(row => row.dataset.visitId)"
        )
        assert set(actual) == {row["id"] for row in records[:3]}
        page.locator("#visits-prev").click()
        expect(page.locator("#visits-page")).to_have_text("1–20 / 23")
        page.locator("#visits-next").click()
        expect(page.locator("#visits-page")).to_have_text("21–23 / 23")
        for count in [2, 1, 20]:
            page.once("dialog", lambda dialog: dialog.accept())
            page.locator("#visit-rows tr[data-visit-id] button").first.click()
            expect(page.locator("#visit-rows tr[data-visit-id]")).to_have_count(count)
        expect(page.locator("#visits-page")).to_have_text("1–20 / 20")
        expect(page.locator("#visits-prev")).to_be_disabled()
        expect(page.locator("#visits-next")).to_be_disabled()


def test_unconfirmed_save_times_out_without_fake_success(live_app):
    with visit_user(live_app) as (page, engine, _actor, ids, _base):
        visits_page(page, 390)
        fill_visit(page, ids)
        routes = []

        def hold(route):
            routes.append(route)

        page.route("**/visits", hold)
        try:
            page.locator("#visit-save").click()
            wait_for_held(page, routes)
            expect(page.locator("#visit-save")).to_be_disabled()
            expect(page.locator("#visit-warn")).to_contain_text(
                "Save could not be confirmed.", timeout=22000
            )
            expect(page.locator("#visit-save")).to_be_enabled()
            expect(page.locator("#visit-notes")).to_have_value("S8 private field note")
            with engine.connect() as db:
                assert (
                    db.execute(
                        text(
                            "SELECT count(*) FROM sales.customer_stock_visit WHERE customer_id=:c"
                        ),
                        {"c": ids["customer"]},
                    ).scalar_one()
                    == 0
                )
        finally:
            page.unroute("**/visits", hold)


def test_stale_previous_stock_cannot_refill_after_selection_cleared(live_app):
    with visit_user(live_app) as (page, _engine, _actor, ids, base):
        seeded_visit(page, base, ids)
        visits_page(page, 390)
        page.evaluate("""() => {
            const real = window.fetch;
            window.__s8StockConsumed = false;
            window.fetch = async function (url, options) {
                const response = await real.apply(this, arguments);
                if (String(url).startsWith('/visits/held-stock?')) {
                    const consume = response.text.bind(response);
                    response.text = async function () {
                        const value = await consume(); window.__s8StockConsumed = true; return value;
                    };
                }
                return response;
            };
        }""")
        held = []

        def hold(route):
            response = route.fetch()
            assert response.status == 200
            held.append((route, response))
            page.evaluate("window.__s8StockHeld = true")

        page.route("**/visits/held-stock?*", hold)
        try:
            page.locator("#visit-customer").select_option(str(ids["customer"]))
            page.locator("#visit-product").select_option(str(ids["product"]))
            wait_for_held(page, held)
            page.locator("#visit-product").select_option("")
            expect(page.locator("#visit-prev")).to_have_value("")
            route, response = held.pop()
            route.fulfill(response=response)
            page.wait_for_function("window.__s8StockConsumed === true")
            page.evaluate(
                "() => new Promise(resolve => requestAnimationFrame(() => resolve(true)))"
            )
            expect(page.locator("#visit-prev")).to_have_value("")
            expect(page.locator("#visit-stock-hint")).to_be_empty()
        finally:
            for route, response in held:
                route.fulfill(response=response)
            page.unroute("**/visits/held-stock?*", hold)


def test_updated_visit_shell_avoids_unversioned_legacy_assets(live_app):
    with visit_user(live_app) as (page, _engine, _actor, _ids, _base):

        def stale(route):
            route.fulfill(
                status=200,
                content_type="text/javascript",
                body="throw new Error('S8 stale unversioned asset requested');",
            )

        page.route("**/app/app.js", stale)
        try:
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#home-view")).to_be_visible()
            script = page.locator('script[src^="app.js"]').get_attribute("src")
            assert "?v=" in script
            observed = page.evaluate(
                "performance.getEntriesByType('resource').map(item => item.name)"
            )
            dictionary_requests = [url for url in observed if "/app/i18n/" in url]
            assert dictionary_requests and all(
                "?v=" in url for url in dictionary_requests
            )
        finally:
            page.unroute("**/app/app.js", stale)
