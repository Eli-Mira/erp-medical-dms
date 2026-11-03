"""Current-contract unequal-account isolation for a late real invoice response.

Additional GREEN-first coverage; original logout RED/GREEN oracle is unchanged.
"""

from uuid import uuid4

from browser_readiness import wait_for_held
from playwright.sync_api import expect
from sqlalchemy.orm import Session
from test_customer_pwa import _browser_user
from test_lane2_balance_history_browser import (
    require_owned_database_before_module_seed as require_owned_database_before_module_seed,  # noqa: PLC0414
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414
from test_zz_i1_browser import i1_dataset as i1_dataset  # noqa: PLC0414


def test_late_invoice_reply_cannot_cross_to_forbidden_warehouse_account(
    live_app, i1_dataset
):
    from app.auth.repo import create_user

    reader = "beta3_warehouse_" + uuid4().hex[:12]
    password = "Synthetic-Beta3-Reader-2026!"
    with Session(live_app[1]) as db:
        create_user(db, reader, password, role="warehouse_staff", is_owner=False)
        db.commit()
    data = i1_dataset
    invoice_path = "/invoices/" + str(data["invoice"])
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        token = page.evaluate("localStorage.getItem('token')")
        witness = page.request.get(
            live_app[0] + invoice_path, headers={"Authorization": "Bearer " + token}
        )
        assert witness.status == 200
        invoice = witness.json()
        assert invoice["id"] == str(data["invoice"])
        page.evaluate(
            "rows => localStorage.setItem('medsys.drafts.v1', JSON.stringify(rows))",
            [
                {
                    "id": invoice["id"],
                    "invoice_no": invoice["invoice_no"],
                    "customer": "Synthetic customer",
                    "grand_total": invoice["grand_total"],
                }
            ],
        )
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        expect(page.locator("#home-aging .aging-cell")).to_have_count(4)
        row = page.locator("#home-drafts tr").filter(
            has=page.get_by_text(invoice["invoice_no"], exact=True)
        )
        expect(row).to_have_count(1)
        page.evaluate(
            """path => {
          const original = window.fetch;
          window.__invoiceBodyConsumed = false;
          window.fetch = function (...args) {
            return original.apply(window, args).then(response => {
              if (new URL(args[0], location.href).pathname === path) {
                const read = response.text.bind(response);
                response.text = async function () {
                  const body = await read();
                  setTimeout(() => { window.__invoiceBodyConsumed = true; }, 0);
                  return body;
                };
              }
              return response;
            });
          };
        }""",
            invoice_path,
        )
        held = []

        def hold_real_authorized_reply(route):
            response = route.fetch()
            assert response.status == 200
            assert response.json()["id"] == invoice["id"]
            held.append((route, response))
            page.evaluate("window.__invoiceHeld = true")

        page.route("**" + invoice_path, hold_real_authorized_reply)
        row.get_by_role("button", name="Open", exact=True).click()
        wait_for_held(page, held)
        assert len(held) == 1
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        page.locator("#login-username").fill(reader)
        page.locator("#login-password").fill(password)
        page.locator("#login-submit").click()
        expect(page.locator("#home-view")).to_be_visible()
        restricted_token = page.evaluate("localStorage.getItem('token')")
        assert restricted_token and restricted_token != token
        forbidden = page.request.get(
            live_app[0] + invoice_path,
            headers={"Authorization": "Bearer " + restricted_token},
        )
        assert forbidden.status == 403
        route, response = held.pop()
        try:
            route.fulfill(response=response)
            page.wait_for_function("window.__invoiceBodyConsumed === true")
            expect(page.locator("#home-view")).to_be_visible()
            expect(page.locator("#draft-view")).to_be_hidden()
            expect(page.locator("#draft-view")).not_to_contain_text(
                invoice["invoice_no"]
            )
            assert page.evaluate("localStorage.getItem('token')") == restricted_token
        finally:
            response.dispose()
