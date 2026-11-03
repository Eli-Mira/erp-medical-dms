"""Shared-browser contact privacy when an authorized refresh fails after login."""

from uuid import uuid4

import pytest
from browser_readiness import wait_for_held
from playwright.sync_api import expect
from sqlalchemy.orm import Session
from test_customer_contact_pwa import seed_customer
from test_customer_pwa import _browser_user, customer_page, references
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


@pytest.mark.parametrize("delivery", ["failed_refresh", "late_owner_response"])
def test_contact_cache_does_not_cross_authenticated_users(live_app, delivery):
    from app.auth.repo import create_user

    branch, territory = references(live_app[1])
    secret = "SYNTHETIC-CONTACT-PRIVATE-" + uuid4().hex[:8]
    cid = seed_customer(live_app[1], branch, territory, address=secret)
    username = "contact_reader_" + uuid4().hex[:10]
    password = "Synthetic-Contact-Reader-2026!"
    with Session(live_app[1]) as db:
        create_user(db, username, password, role="finance", is_owner=False)
        db.commit()
    with _browser_user(live_app, width=390) as (page, _engine, _owner):
        customer_page(page, 390)
        expect(page.locator(f'tr[data-customer-id="{cid}"]')).to_contain_text(secret)
        held = []
        prior = None
        if delivery == "late_owner_response":

            def hold_owner_read(route):
                if route.request.method == "GET" and not held:
                    held.append(route)
                else:
                    route.continue_()

            page.route("**/master/customers*", hold_owner_read)
            with page.expect_request(
                lambda r: "/master/customers" in r.url and r.method == "GET"
            ):
                page.locator('[data-refresh="customers"]').click()
            wait_for_held(page, held)
            prior = held[0].fetch()
            assert prior.status == 200 and any(row["id"] == cid for row in prior.json())
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        page.locator("#login-username").fill(username)
        page.locator("#login-password").fill(password)
        page.locator("#login-submit").click()
        expect(page.locator("#home-view")).to_be_visible()
        token = page.evaluate("localStorage.getItem('token')")
        actual = page.request.get(
            live_app[0] + "/master/customers",
            headers={"Authorization": "Bearer " + token},
        )
        assert actual.status == 200 and actual.json() == []
        observed_routes = []

        def fail_route(route):
            observed_routes.append(route)
            return route.fulfill(
                status=503,
                content_type="application/json",
                body='{"detail":"Synthetic scoped refresh failure"}',
            )

        page.route("**/master/customers*", fail_route)
        customer_page(page, 390)
        wait_for_held(page, observed_routes)
        expect(page.locator("#customers-error")).to_contain_text(
            "Synthetic scoped refresh failure"
        )
        if prior is not None:
            old_auth = held[0].request.headers["authorization"]
            with page.expect_response(
                lambda r: (
                    r.request.headers.get("authorization") == old_auth
                    and "/master/customers" in r.url
                )
            ) as late:
                held[0].fulfill(response=prior)
            late.value.finished()
            # Flush the completed response's DOM work before asserting absence.
            page.evaluate(
                "() => new Promise(resolve => requestAnimationFrame(resolve))"
            )
        expect(page.locator(f'tr[data-customer-id="{cid}"]')).to_have_count(0)
        expect(page.locator("#customers-view")).not_to_contain_text(secret)
        expect(page.locator("[data-customer-edit]")).to_have_count(0)


@pytest.mark.parametrize("ending", ["expired", "logout_pending", "logout_failure"])
def test_contact_session_end_clears_directory_and_form(live_app, ending):
    from sqlalchemy import text

    branch, territory = references(live_app[1])
    secret = "SYNTHETIC-SESSION-END-" + uuid4().hex[:8]
    cid = seed_customer(live_app[1], branch, territory, address=secret)
    held = []
    with _browser_user(live_app) as (page, engine, owner):
        customer_page(page, 1440)
        row = page.locator(f'tr[data-customer-id="{cid}"]')
        expect(row).to_contain_text(secret)
        row.locator("[data-customer-edit]").click()
        expect(page.locator("#customer-save")).to_be_enabled()
        if ending == "expired":
            token = page.evaluate("localStorage.getItem('token')")
            with engine.begin() as db:
                changed = db.execute(
                    text(
                        "UPDATE platform.platform_session SET expires_at=now()-interval '1 second' WHERE id=:sid AND user_id=:uid"
                    ),
                    {"sid": token, "uid": owner},
                )
                assert changed.rowcount == 1
            page.locator("#customer-address").fill(secret + " edited")
            with page.expect_response(
                lambda r: (
                    r.request.method == "PATCH"
                    and r.url.endswith("/master/customers/" + cid)
                )
            ) as denied:
                page.locator("#customer-save").click()
            assert denied.value.status == 401
        else:
            page.locator("#customer-cancel").click()
            if ending == "logout_pending":
                page.route("**/auth/logout", lambda route: held.append(route))
            else:
                observed_routes = []

                def fail_route(route):
                    observed_routes.append(route)
                    return route.fulfill(
                        status=503,
                        content_type="application/json",
                        body='{"detail":"Synthetic logout outage"}',
                    )

                page.route("**/auth/logout", fail_route)
            page.locator("#logout").click()
        try:
            expect(page.locator("#login-view")).to_be_visible()
            assert page.evaluate("localStorage.getItem('token')") is None
            expect(row).to_have_count(0)
            expect(page.locator("#customer-address")).to_have_value("")
            expect(page.locator("#customer-dialog")).not_to_be_visible()
            expect(page.locator(f'#customer option[value="{cid}"]')).to_have_count(0)
            if ending == "logout_pending":
                wait_for_held(page, held)
            elif ending == "logout_failure":
                wait_for_held(page, observed_routes)
        finally:
            for route in held:
                route.fulfill(
                    status=200, content_type="application/json", body='{"ok":true}'
                )


@pytest.mark.parametrize("delivery", ["success", "error"])
def test_late_boot_customer_data_cannot_cross_rapid_account_switches(
    live_app, delivery
):
    from app.auth.repo import create_user

    branch, territory = references(live_app[1])
    secret = "SYNTHETIC-BOOT-PRIVATE-" + uuid4().hex[:8]
    cid = seed_customer(live_app[1], branch, territory, address=secret)
    reader = "recovery_reader_" + uuid4().hex[:10]
    password = "Synthetic-Contact-Reader-2026!"
    with Session(live_app[1]) as db:
        create_user(db, reader, password, role="finance", is_owner=False)
        db.commit()
    with _browser_user(live_app) as (page, _engine, _owner):
        token = page.evaluate("localStorage.getItem('token')")
        owner = page.request.get(
            live_app[0] + "/auth/me", headers={"Authorization": "Bearer " + token}
        ).json()["username"]
        held = []

        def hold_boot(route):
            if route.request.method == "GET" and not held:
                held.append(route)
            else:
                route.continue_()

        page.route("**/master/customers*", hold_boot)
        page.add_init_script("""(() => {
            const oldToken = localStorage.getItem('token');
            const original = window.fetch;
            window.fetch = async (...args) => {
                const response = await original(...args);
                if (args[0] === '/master/customers' && args[1].headers.Authorization === 'Bearer ' + oldToken) {
                    const read = response.text.bind(response);
                    response.text = async () => {
                        const value = await read();
                        window.__privacyOldReadConsumed = true;
                        return value;
                    };
                }
                return response;
            };
        })();""")
        with page.expect_request(
            lambda r: r.method == "GET" and r.url.endswith("/master/customers")
        ):
            page.reload(wait_until="domcontentloaded")
        expect(page.locator("#logout")).to_be_visible()
        wait_for_held(page, held)
        assert len(held) == 1
        prior = held[0].fetch()
        assert prior.status == 200 and any(row["id"] == cid for row in prior.json())
        old_auth = held[0].request.headers["authorization"]
        for username, pwd in [
            (reader, password),
            (owner, "Synthetic-Customer-Test-2026!"),
            (reader, password),
        ]:
            page.locator("#logout").click()
            expect(page.locator("#login-view")).to_be_visible()
            page.locator("#login-username").fill(username)
            page.locator("#login-password").fill(pwd)
            page.locator("#login-submit").click()
            expect(page.locator("#home-view")).to_be_visible()
        current = page.evaluate("localStorage.getItem('token')")
        actual = page.request.get(
            live_app[0] + "/master/customers",
            headers={"Authorization": "Bearer " + current},
        )
        assert actual.status == 200 and actual.json() == []
        customer_page(page, 1440)
        with page.expect_response(
            lambda r: (
                r.request.headers.get("authorization") == old_auth
                and r.url.endswith("/master/customers")
            )
        ) as late:
            if delivery == "success":
                held[0].fulfill(response=prior)
            else:
                held[0].fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"detail":"Synthetic old bootstrap failure"}',
                )
        late.value.finished()
        page.wait_for_function("window.__privacyOldReadConsumed === true")
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
        assert page.evaluate("localStorage.getItem('token')") == current
        expect(page.locator(f'#customer option[value="{cid}"]')).to_have_count(0)
        expect(page.locator("#customers-view")).not_to_contain_text(secret)
        page.locator('#sidebar [data-view="home"]').first.click()
        customer_page(page, 1440)
        expect(page.locator(f'tr[data-customer-id="{cid}"]')).to_have_count(0)
        expect(page.locator("#customers-view")).not_to_contain_text(secret)
