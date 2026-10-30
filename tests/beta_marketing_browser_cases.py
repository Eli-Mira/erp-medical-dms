"""Real-response browser regressions for marketing's asynchronous consumers.

Called by the owned disposable-PG fixture, never against a default database.
"""

from urllib.parse import urlsplit
from uuid import uuid4

from playwright.sync_api import expect

CASE_NAMES = (
    "selection-during-product-lookup",
    "mode-change-during-detail-read",
    "newer-record-open-wins",
    "refresh-during-committed-save",
    "old-owner-list-after-scoped-login",
)


def capture_response(page, path, method="GET", search=""):
    """Delay one genuine HTTP response; observe its actual text consumption."""
    page.evaluate(
        """({path, method, search}) => {
          if (!window.__raceFetchInstalled) {
            const original = window.fetch.bind(window);
            window.fetch = async function(input, options) {
              const probe = window.__marketingRace;
              const u = new URL(typeof input === 'string' ? input : input.url, location.href);
              const m = (options && options.method || input.method || 'GET').toUpperCase();
              const chosen = probe && !probe.claimed && u.pathname === probe.path &&
                m === probe.method && (probe.search === null || u.search === probe.search);
              if (chosen) probe.claimed = true;
              const response = await original(input, options);
              if (chosen) {
                const read = response.text.bind(response);
                response.text = async function() {
                  const value = await read();
                  probe.consumed = true;
                  return value;
                };
              }
              return response;
            };
            window.__raceFetchInstalled = true;
          }
          window.__marketingRace = {path, method, search, claimed:false, held:false, consumed:false};
        }""",
        {"path": path, "method": method, "search": search},
    )
    held = []

    def route_handler(route):
        parsed = urlsplit(route.request.url)
        actual_search = "?" + parsed.query if parsed.query else ""
        if (
            not held
            and parsed.path == path
            and route.request.method == method
            and (search is None or actual_search == search)
        ):
            response = route.fetch()
            assert response.status in (200, 201), (
                "captured real status",
                response.status,
            )
            held.append((route, response))
            page.evaluate("window.__marketingRace.held = true")
        else:
            route.continue_()

    page.route("**/*", route_handler)

    def wait():
        page.wait_for_function("window.__marketingRace.held", timeout=15000)
        assert len(held) == 1
        return held[0][1]

    def release():
        wait()
        held[0][0].fulfill(response=held[0][1])
        page.unroute("**/*", route_handler)
        page.wait_for_function("window.__marketingRace.consumed", timeout=15000)
        # The actual client parses text then renders in promise continuations.
        page.evaluate(
            "() => Promise.resolve().then(() => new Promise(requestAnimationFrame))"
        )

    return wait, release


def ready(page, navigate):
    navigate(page, "marketing")
    form = page.locator("#marketing-editor form")
    expect(form.locator("button[type=submit]")).to_be_enabled()
    expect(form.locator("[name=product_ids] option")).not_to_have_count(0)
    return form


def create_spend(http, owner, amount="11.11", territory=None, note=None):
    payload = {
        "spend_date": "2026-10-15",
        "amount": amount,
        "activity_type": "SYNTH-RACE-" + uuid4().hex[:10],
        "notes": note,
        "product_ids": [],
        "territory_id": territory,
    }
    response = http.post("/marketing/spend", headers=owner, json=payload)
    assert response.status_code == 201, (
        "synthetic spend admission",
        response.status_code,
    )
    row = response.json()
    assert row["amount"] == amount
    return row


def run_case(name, page, http, owner, rep, products, territories, navigate, password):
    assert name in CASE_NAMES
    if name == "selection-during-product-lookup":
        form = ready(page, navigate)
        chosen = form.locator("[name=product_ids]")
        first, second = products[:2]
        expect(chosen.locator('option[value="' + second["id"] + '"]')).to_have_count(1)
        chosen.select_option(first["id"])
        wait, release = capture_response(page, "/master/products", search=None)
        search = form.locator("[name=product_search]")
        search.fill(first["sku"])
        search.press("Tab")
        response = wait()
        assert first["id"] in {r["id"] for r in response.json()}
        chosen.select_option(second["id"])
        release()
        assert chosen.evaluate("e => [...e.selectedOptions].map(o=>o.value)") == [
            second["id"]
        ]
    elif name == "mode-change-during-detail-read":
        row = create_spend(http, owner)
        ready(page, navigate)
        button = page.locator("#marketing-editor button").filter(has_text=row["id"])
        expect(button).to_be_visible()
        wait, release = capture_response(page, "/marketing/spend/" + row["id"])
        button.click()
        wait()
        page.locator("#marketing-editor > select").select_option("objectives")
        field = page.locator("#marketing-editor [name=objective]")
        expect(field).to_be_visible()
        wanted = "SYNTH-PRESERVE-OBJECTIVE-" + uuid4().hex[:8]
        field.fill(wanted)
        release()
        expect(field).to_have_value(wanted)
    elif name == "newer-record-open-wins":
        first = create_spend(http, owner, "11.11")
        second = create_spend(http, owner, "22.22")
        ready(page, navigate)
        buttons = page.locator("#marketing-editor button")
        wait, release = capture_response(page, "/marketing/spend/" + first["id"])
        buttons.filter(has_text=first["id"]).click()
        wait()
        buttons.filter(has_text=second["id"]).click()
        field = page.locator("#marketing-editor [name=amount]")
        expect(field).to_have_value("22.22")
        release()
        expect(field).to_have_value("22.22")
    elif name == "refresh-during-committed-save":
        form = ready(page, navigate)
        form.evaluate("e => e.dataset.raceOld = '1'")
        form.locator("[name=spend_date]").fill("2026-10-15")
        form.locator("[name=amount]").fill("9.99")
        form.locator("[name=activity_type]").fill("SYNTH-SAVE-" + uuid4().hex[:8])
        wait, release = capture_response(page, "/marketing/spend", method="POST")
        form.locator("button[type=submit]").click()
        response = wait()
        assert response.status == 201
        page.locator('[data-refresh="marketing"]').click()
        if page.locator('#marketing-editor form[data-race-old="1"]').count() == 0:
            expect(page.locator("#marketing-editor fieldset")).to_have_attribute(
                "disabled", ""
            )
        release()
        expect(page.locator("#marketing-editor button[type=submit]")).to_be_enabled()
    else:
        allowed = http.get("/master/territories", headers=rep)
        assert allowed.status_code == 200
        permitted = {row["id"] for row in allowed.json()}
        outside = next(row["id"] for row in territories if row["id"] not in permitted)
        canary = "SYNTH-MARKETING-OWNER-ONLY-" + uuid4().hex
        private = create_spend(http, owner, territory=outside, note=canary)
        current = http.get("/marketing/spend", headers=rep)
        assert current.status_code == 200 and private["id"] not in {
            r["id"] for r in current.json()
        }
        ready(page, navigate)
        expect(page.locator("#marketing-rows")).to_contain_text(canary)
        wait, release = capture_response(page, "/marketing/spend")
        page.locator('[data-refresh="marketing"]').click()
        response = wait()
        assert private["id"] in {r["id"] for r in response.json()}
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        cleared_at_logout = (
            page.locator("#marketing-rows").inner_text() == ""
            and page.locator("#marketing-editor").inner_text() == ""
        )
        page.locator("#login-username").fill("fresh_rep_mona")
        page.locator("#login-password").fill(password)
        page.locator("#login-submit").click()
        expect(page.locator("#home-view")).to_be_visible()
        navigate(page, "marketing")
        expect(page.locator("#marketing-editor button[type=submit]")).to_be_disabled()
        current_token = page.evaluate("localStorage.getItem('token')")
        assert current_token
        release()
        assert page.evaluate("localStorage.getItem('token')") == current_token
        expect(page.locator("#marketing-rows")).not_to_contain_text(canary)
        expect(page.locator("#marketing-editor")).not_to_contain_text(private["id"])
        assert cleared_at_logout, (
            "Marketing rows/editor must clear immediately on session teardown"
        )
