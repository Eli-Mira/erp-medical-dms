"""Real saved financial reads must be latest-request-wins within one session."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect
from sqlalchemy import text
from test_customer_pwa import _browser_user
from test_lane2_balance_history_browser import (
    require_owned_database_before_module_seed as require_owned_database_before_module_seed,  # noqa: PLC0414
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414
from test_zz_i1_browser import i1_dataset as i1_dataset  # noqa: PLC0414


def observe_body_consumption(page, path):
    page.evaluate(
        """path => {
      const original = window.fetch;
      window.__orderingBodiesConsumed = 0;
      window.fetch = function (...args) {
        return original.apply(window, args).then(response => {
          if (new URL(args[0], location.href).pathname === path) {
            const read = response.text.bind(response);
            response.text = async function () {
              const body = await read();
              setTimeout(() => { ++window.__orderingBodiesConsumed; }, 0);
              return body;
            };
          }
          return response;
        });
      };
    }""",
        path,
    )


def test_overlapping_same_customer_statements_do_not_append_duplicate_rows(
    live_app, i1_dataset
):
    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, engine, _owner):
        with engine.connect() as witness:
            expected_rows = witness.scalar(
                text(
                    "SELECT count(*) FROM finance.ar_entry WHERE customer_id=:customer"
                ),
                {"customer": data["customer"]},
            )
        assert expected_rows > 0
        page.locator('#sidebar [data-view="balances"]').click()
        expect(page.locator("#entry-rows tr")).to_have_count(expected_rows)
        expect(page.locator("#entry-rows")).to_contain_text(data["prefix"])
        expect(page.locator("#ledger-summary .badge")).to_have_count(5)
        page.evaluate("""() => {
          const original = window.fetch;
          window.__statementPendingBodies = 0;
          window.fetch = function (...args) {
            const path = new URL(args[0], location.href).pathname;
            const tracked = path === '/ar/entries' || path.startsWith('/invoices/');
            if (tracked) ++window.__statementPendingBodies;
            return original.apply(window, args).then(response => {
              if (tracked) {
                const read = response.text.bind(response);
                response.text = async function () {
                  try { return await read(); }
                  finally { setTimeout(() => { --window.__statementPendingBodies; }, 0); }
                };
              }
              return response;
            }, error => {
              if (tracked) --window.__statementPendingBodies;
              throw error;
            });
          };
        }""")
        # Same-turn native change events overlap the real async renderer even with warm caches.
        # The zero-delay turn drains only resolved cache microtasks; real fetches use body barriers.
        page.evaluate("""async () => {
          const picker = document.getElementById('ledger-customer');
          picker.dispatchEvent(new Event('change', {bubbles: true}));
          picker.dispatchEvent(new Event('change', {bubbles: true}));
          await new Promise(resolve => setTimeout(resolve, 0));
        }""")
        page.wait_for_function("window.__statementPendingBodies === 0")
        expect(page.locator("#entry-rows tr")).to_have_count(expected_rows)
        expect(page.locator("#ledger-summary .badge")).to_have_count(5)


@pytest.mark.parametrize("expectation", ["latest_balance", "fresh_statement"])
def test_older_balance_reply_cannot_overwrite_new_persisted_collection(
    live_app, i1_dataset, monkeypatch, expectation
):
    from app import config
    from app.finance import payment_router
    from app.main import app

    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, engine, _owner):
        expect(page.locator("#home-aging .aging-cell")).to_have_count(4)
        token = page.evaluate("localStorage.getItem('token')")
        auth = {"Authorization": "Bearer " + token}
        invoice = page.request.get(
            live_app[0] + "/invoices/" + str(data["invoice"]), headers=auth
        )
        assert invoice.status == 200
        observe_body_consumption(page, "/ar/balances")
        held, requests = [], []
        old_balance = []

        def hold_only_first_actual_balance_reply(route):
            requests.append(route.request.url)
            if len(requests) != 1:
                route.continue_()
                return
            response = route.fetch()
            assert response.status == 200
            row = next(
                r for r in response.json() if r["customer_id"] == str(data["customer"])
            )
            old_balance.append(Decimal(row["balance"]))
            held.append((route, response))
            page.evaluate("window.__olderBalanceHeld = true")

        page.route("**/ar/balances", hold_only_first_actual_balance_reply)
        page.locator('#sidebar [data-view="balances"]').click()
        page.wait_for_function("window.__olderBalanceHeld === true")
        # Positive collection is restricted to this module's exact owned UUID test DB.
        assert (
            config.POSTING_ENABLED is False and payment_router.POSTING_ENABLED is False
        )
        with monkeypatch.context() as scoped:
            scoped.setattr(config, "POSTING_ENABLED", True)
            scoped.setattr(payment_router, "POSTING_ENABLED", True)
            with TestClient(app) as harness_client:
                result = harness_client.post(
                    "/collections",
                    headers=auth,
                    json={
                        "invoice_id": str(data["invoice"]),
                        "invoice_version": invoice.json()["version"],
                        "receipt_no": "BETA3-ORDER-" + uuid4().hex[:12],
                        "receipt_date": invoice.json()["invoice_date"],
                        "amount": "1.00",
                        "method": "cash",
                    },
                )
                assert result.status_code == 201
        assert (
            config.POSTING_ENABLED is False and payment_router.POSTING_ENABLED is False
        )
        with engine.connect() as witness:
            customer_name = witness.scalar(
                text(
                    "SELECT name_ar FROM master_data.master_customer WHERE id=:customer"
                ),
                {"customer": data["customer"]},
            )
            assert (
                witness.scalar(
                    text(
                        "SELECT count(*) FROM master_data.master_customer WHERE name_ar=:name"
                    ),
                    {"name": customer_name},
                )
                == 1
            )
            expected_rows = witness.scalar(
                text(
                    "SELECT count(*) FROM finance.ar_entry WHERE customer_id=:customer"
                ),
                {"customer": data["customer"]},
            )
            expected = witness.scalar(
                text(
                    "SELECT sum(debit-credit) FROM finance.ar_entry WHERE customer_id=:customer"
                ),
                {"customer": data["customer"]},
            )
        assert expected == old_balance[0] - Decimal("1.00")
        page.locator('[data-refresh="balances"]').click()
        page.wait_for_function("window.__orderingBodiesConsumed === 1")
        row = page.locator("#balance-rows tr").filter(
            has=page.get_by_text(customer_name, exact=True)
        )
        expect(row).to_have_count(1)
        expect(row.locator("td").nth(2)).to_have_text(format(expected, ".2f"))
        assert len(requests) == 2
        route, response = held.pop()
        try:
            if expectation == "fresh_statement":
                expect(page.locator("#entry-rows tr")).to_have_count(expected_rows)
                expect(page.locator("#ledger-summary .badge").first).to_have_text(
                    "Balance: " + format(expected, ".2f")
                )
            route.fulfill(response=response)
            page.wait_for_function("window.__orderingBodiesConsumed === 2")
            expect(row.locator("td").nth(2)).to_have_text(format(expected, ".2f"))
        finally:
            response.dispose()
