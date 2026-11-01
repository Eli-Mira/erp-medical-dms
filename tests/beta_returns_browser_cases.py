"""Real Returns PWA controls; called only by the owned contained fixture."""

from decimal import Decimal
from urllib.parse import urlsplit

from playwright.sync_api import expect
from sqlalchemy import text


def run_cases(f, browser, http, owner, customer, warehouse, product, batch, baseline):
    for username, locale, width in [
        ("fresh_owner", "ar", 390),
        ("fresh_owner", "en", 1440),
        ("fresh_beta_finance", "ar", 390),
        ("fresh_beta_finance", "en", 1440),
    ]:
        context, page = f.browser_login(browser, username, locale, width)
        errors = []
        page.on(
            "pageerror",
            lambda error, errors=errors: errors.append(f.clean_message(error)),
        )
        tag = "returns." + username + "." + locale + "." + str(width)
        saved = {}
        try:

            def create(page=page, tag=tag, saved=saved, username=username):
                f.navigate(page, "returns")
                button = page.locator("#return-form button[type=submit]")
                expect(button).to_be_enabled()
                expect(
                    page.locator("#returns-view .badge").filter(has_text="Beta").first
                ).to_be_visible()
                page.locator("#return-customer").select_option(customer["id"])
                page.locator("#return-product").select_option(product["id"])
                page.locator("#return-warehouse").select_option(warehouse["id"])
                page.locator("#return-batch").select_option(batch["id"])
                page.locator("#return-quantity").fill("1.125")
                page.locator("#return-date").fill("2026-10-15")
                page.locator("#return-reason").fill("SYNTH-RETURN-" + tag)
                with page.expect_response(
                    lambda r: (
                        urlsplit(r.url).path == "/returns"
                        and r.request.method == "POST"
                    )
                ) as got:
                    button.click()
                response = got.value
                assert response.status == 201
                sent = response.request.post_data_json
                assert sent["quantity"] == "1.125"
                assert sent["batch_id"] == batch["id"]
                assert not {"status", "approved_by", "created_by", "unit_cost"} & set(
                    sent
                )
                saved.update(response.json())
                assert (
                    saved["customer_id"] == customer["id"]
                    and saved["warehouse_id"] == warehouse["id"]
                )
                assert (
                    saved["product_id"] == product["id"]
                    and saved["batch_id"] == batch["id"]
                )
                assert saved["status"] == "quarantined" and Decimal(
                    saved["quantity"]
                ) == Decimal("1.125")
                expect(page.locator("#return-detail")).to_contain_text(saved["id"])
                expect(page.locator("#return-quantity")).to_have_value("")
                with f.engine.connect() as db:
                    row = (
                        db.execute(
                            text(
                                "SELECT quantity,status,created_by FROM sales.sales_return WHERE id=:i"
                            ),
                            {"i": saved["id"]},
                        )
                        .mappings()
                        .one()
                    )
                    actor = db.execute(
                        text("SELECT id FROM platform.platform_user WHERE username=:u"),
                        {"u": username},
                    ).scalar_one()
                    assert (
                        row["quantity"] == Decimal("1.125")
                        and row["status"] == "quarantined"
                        and row["created_by"] == actor
                    )
                    audit = (
                        db.execute(
                            text(
                                "SELECT actor_user_id,new_values FROM audit.audit_log WHERE entity_type='sales_return' AND entity_id=:i"
                            ),
                            {"i": saved["id"]},
                        )
                        .mappings()
                        .one()
                    )
                    assert (
                        audit["actor_user_id"] == actor
                        and audit["new_values"]["status"] == "quarantined"
                    )
                assert f.business_snapshot() == baseline
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth + 1"
                )

            f.check(
                tag
                + ".actual-intake-exact-PG-quarantine-audit-no-saleable-financial-change",
                create,
            )

            def reopen(page=page, tag=tag, saved=saved):
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("#home-view")).to_be_visible()
                f.navigate(page, "returns")
                row = page.locator(
                    '#return-rows tr[data-return-id="' + saved["id"] + '"]'
                )
                expect(row).to_have_count(1)
                row.locator("button").click()
                expect(page.locator("#return-detail")).to_contain_text(saved["id"])
                expect(page.locator("#return-detail")).to_contain_text("1.125")
                listed = http.get("/returns", headers=owner)
                assert listed.status_code == 200
                found = next(row for row in listed.json() if row["id"] == saved["id"])
                assert (
                    isinstance(found["quantity"], str) and found["quantity"] == "1.125"
                )
                assert f.business_snapshot() == baseline
                page.screenshot(path=str(f.OUT / (tag + ".png")))

            f.check(tag + ".real-reopen-after-reload-exact-quantity-wire", reopen)

            def stale_read_logout(page=page, context=context):
                page.evaluate("""() => {
                    const nativeFetch = window.fetch;
                    window.__returnHeld = false; window.__returnConsumed = false;
                    const gate = new Promise(resolve => { window.__returnRelease = resolve; });
                    window.fetch = async (...args) => {
                        const response = await nativeFetch(...args);
                        if (String(args[0]).startsWith('/returns?') && !window.__returnHeld) {
                            const readText = response.text.bind(response);
                            response.text = async () => {
                                const body = await readText(); window.__returnHeld = true;
                                await gate; window.__returnConsumed = true; return body;
                            };
                        }
                        return response;
                    };
                }""")
                page.locator('#returns-view [data-refresh="returns"]').click()
                page.wait_for_function("window.__returnHeld === true")

                def fail_logout(route):
                    route.abort("failed")

                context.route("**/auth/logout", fail_logout)
                try:
                    page.locator("#logout").click()
                    expect(page.locator("#login-view")).to_be_visible()
                    assert page.locator("#return-editor").text_content() == ""
                    assert page.locator("#return-detail").text_content() == ""
                    assert page.locator("#return-rows tr").count() == 0
                    page.locator("#login-username").fill("fresh_rep_mona")
                    page.locator("#login-password").fill(f.password)
                    page.locator("#login-submit").click()
                    expect(page.locator("#home-view")).to_be_visible()
                    current = http.post(
                        "/auth/login",
                        json={"username": "fresh_rep_mona", "password": f.password},
                    )
                    assert current.status_code == 200
                    token = current.json()["access_token"]
                    f.tokens.add(token)
                    assert (
                        http.get(
                            "/returns", headers={"Authorization": "Bearer " + token}
                        ).status_code
                        == 403
                    )
                    page.evaluate("window.__returnRelease()")
                    page.wait_for_function("window.__returnConsumed === true")
                    page.evaluate(
                        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
                    )
                    assert page.locator("#return-editor").text_content() == ""
                    assert page.locator("#return-detail").text_content() == ""
                    assert page.locator("#return-rows tr").count() == 0
                    assert f.business_snapshot() == baseline
                finally:
                    context.unroute("**/auth/logout", fail_logout)

            f.check(
                tag
                + ".real-failed-logout-account-swap-and-consumed-late-body-no-private-repopulation",
                stale_read_logout,
            )
            f.check(
                tag + ".no-runtime-errors",
                lambda errors=errors: require(not errors, errors),
            )
        finally:
            context.close()

    context, page = f.browser_login(browser, "fresh_owner", "en", 1440)
    try:

        def uncertain():
            f.navigate(page, "returns")
            expect(page.locator("#return-form button[type=submit]")).to_be_enabled()
            for selector, value in [
                ("customer", customer["id"]),
                ("product", product["id"]),
                ("warehouse", warehouse["id"]),
            ]:
                page.locator("#return-" + selector).select_option(value)
            page.locator("#return-quantity").fill("1.125")

            def abort_create(route):
                if route.request.method == "POST":
                    route.abort("failed")
                else:
                    route.continue_()

            context.route("**/returns", abort_create)
            try:
                page.locator("#return-form button[type=submit]").click()
                expect(page.locator("#returns-error")).to_be_visible()
                expect(
                    page.locator("#return-form button[type=submit]")
                ).to_be_disabled()
                marker = page.evaluate("sessionStorage.getItem('return-pending')")
                assert (
                    marker
                    and page.evaluate(
                        "sessionStorage.getItem('return-pending').includes(localStorage.getItem('token'))"
                    )
                    is False
                )
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("#home-view")).to_be_visible()
                f.navigate(page, "returns")
                expect(
                    page.locator("#return-form button[type=submit]")
                ).to_be_disabled()
                assert (
                    page.evaluate("sessionStorage.getItem('return-pending')") == marker
                )
                assert f.business_snapshot() == baseline
            finally:
                context.unroute("**/returns", abort_create)

        f.check(
            "returns.ambiguous-write-credential-free-lock-survives-real-reload",
            uncertain,
        )
    finally:
        context.close()


def require(condition, details):
    assert condition, details
