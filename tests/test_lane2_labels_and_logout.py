"""Financial Beta labelling and normal-logout financial-data cleanup."""

from html.parser import HTMLParser
from pathlib import Path

from browser_readiness import wait_for_held
from playwright.sync_api import expect
from test_customer_pwa import _browser_user
from test_lane2_balance_history_browser import (
    require_owned_database_before_module_seed as require_owned_database_before_module_seed,  # noqa: PLC0414
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414
from test_zz_i1_browser import i1_dataset as i1_dataset  # noqa: PLC0414


class BetaLabels(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = []
        self.labelled = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.sections.append(attrs.get("id"))
        if attrs.get("data-i18n") == "beta_label" and self.sections:
            self.labelled.add(self.sections[-1])

    def handle_endtag(self, tag):
        if tag == "section":
            self.sections.pop()


def test_invoice_and_collections_flows_carry_explicit_beta_labels():
    parser = BetaLabels()
    parser.feed(
        (Path(__file__).resolve().parents[1] / "web/index.html").read_text(
            encoding="utf-8"
        )
    )
    required = {"invoice-view", "draft-view", "collections-view"}
    assert required <= parser.labelled, (
        "Invoice entry, saved invoice and collections must explicitly say Beta"
    )


def test_logout_clears_rendered_financial_balances_statement_and_receipts(
    live_app, i1_dataset
):
    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        page.locator('#sidebar [data-view="balances"]').click()
        expect(page.locator("#balances-view")).to_be_visible()
        expect(
            page.locator(f'#ledger-customer option[value="{data["customer"]}"]')
        ).to_have_count(1)
        page.locator("#ledger-customer").select_option(str(data["customer"]))
        expect(page.locator("#entry-rows")).to_contain_text(data["prefix"])
        expect(page.locator("#balance-rows tr")).not_to_have_count(0)
        page.locator('#sidebar [data-view="collections"]').click()
        expect(page.locator("#collections-view")).to_be_visible()
        expect(page.locator("#receipt-rows")).to_contain_text(data["prefix"])
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        for element_id in (
            "balance-rows",
            "entry-rows",
            "receipt-rows",
            "ledger-summary",
        ):
            expect(page.locator("#" + element_id)).to_have_text("")
        expect(
            page.locator('#ledger-customer option[value]:not([value=""])')
        ).to_have_count(0)


def test_late_real_balance_reply_cannot_repopulate_logged_out_screen(
    live_app, i1_dataset
):
    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        page.locator('#sidebar [data-view="balances"]').click()
        customer_option = page.locator(
            f'#ledger-customer option[value="{data["customer"]}"]'
        )
        expect(customer_option).to_have_count(1)
        held = []

        def hold_actual_balance_reply(route):
            response = route.fetch()
            assert response.status == 200
            assert any(
                row["customer_id"] == str(data["customer"]) for row in response.json()
            )
            held.append((route, response))
            page.evaluate("window.__balanceReplyHeld = true")

        page.evaluate("""() => {
          const original = window.fetch;
          window.__balanceBodyConsumed = false;
          window.fetch = function (...args) {
            return original.apply(window, args).then(response => {
              if (new URL(args[0], location.href).pathname === '/ar/balances') {
                const read = response.text.bind(response);
                response.text = async function () {
                  const body = await read();
                  setTimeout(() => { window.__balanceBodyConsumed = true; }, 0);
                  return body;
                };
              }
              return response;
            });
          };
        }""")
        page.route("**/ar/balances", hold_actual_balance_reply)
        page.locator('[data-refresh="balances"]').click()
        wait_for_held(page, held)
        assert len(held) == 1
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        assert page.request.get(live_app[0] + "/ar/balances").status == 401
        route, response = held.pop()
        route.fulfill(response=response)
        page.wait_for_function("window.__balanceBodyConsumed === true")
        expect(page.locator("#balance-rows")).to_have_text("")
        expect(customer_option).to_have_count(0)
        response.dispose()
