"""Privacy browser controls; parent native runs supersede rejected host-only evidence.

Source-sensitive replay of a preserved earlier snapshot is not original historical
RED-first chronology. Real PostgreSQL and the approved disposable runner required.
"""

import pytest
from browser_readiness import wait_for_held
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_customer_pwa import _browser_user
from test_lane2_balance_history_browser import (
    require_owned_database_before_module_seed as require_owned_database_before_module_seed,  # noqa: PLC0414
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414
from test_zz_i1_browser import i1_dataset as i1_dataset  # noqa: PLC0414


def test_logout_clears_local_draft_registry_and_home_drafts(live_app, i1_dataset):
    """Logout must remove medsys.drafts.v1 and clear #home-drafts."""
    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        # Seed a synthetic draft row in the local registry.
        page.evaluate(
            "rows => localStorage.setItem('medsys.drafts.v1', JSON.stringify(rows))",
            [
                {
                    "id": str(data["draft"]),
                    "invoice_no": "PRIV-" + data["prefix"],
                    "customer": "Synthetic customer",
                    "grand_total": 123.45,
                }
            ],
        )
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        expect(page.locator("#home-drafts tr")).to_have_count(1)

        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()

        # Registry must be gone.
        registry = page.evaluate(
            "() => JSON.parse(localStorage.getItem('medsys.drafts.v1') || '[]')"
        )
        assert registry == []

        # Home drafts table must be empty.
        expect(page.locator("#home-drafts tr")).to_have_count(0)


def test_logout_clears_draft_view_fields_and_notes(live_app, i1_dataset):
    """Logout erases a real synthetic private note and displayed invoice values."""
    data = i1_dataset
    private_note = "PRIVATE-DRAFT-" + data["prefix"]
    with Session(live_app[1]) as db:
        db.execute(
            text("UPDATE sales.sales_invoice SET notes=:note WHERE id=:id"),
            {"note": private_note, "id": data["draft"]},
        )
        db.commit()
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        # Seed a synthetic draft row in the local registry and reload so home renders it.
        page.evaluate(
            "rows => localStorage.setItem('medsys.drafts.v1', JSON.stringify(rows))",
            [
                {
                    "id": str(data["draft"]),
                    "invoice_no": "PRIV-" + data["prefix"],
                    "customer": "Synthetic customer",
                    "grand_total": 123.45,
                }
            ],
        )
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        expect(page.locator("#home-drafts tr")).to_have_count(1)

        # Open the saved draft from home so draft-view is populated.
        page.locator("#home-drafts button").click()
        expect(page.locator("#draft-view")).to_be_visible()
        expect(page.locator("#draft-notes")).to_have_text(private_note)

        # Now logout.
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()

        # Draft view fields must be cleared, not retain stale text.
        assert (
            page.evaluate(
                "() => document.getElementById('draft-notes')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-lines')?.innerHTML || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-no')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-customer')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-warehouse')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-date')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-status')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-before')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-discount')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-net')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-vat')?.textContent || ''"
            )
            == ""
        )
        assert (
            page.evaluate(
                "() => document.getElementById('draft-grand')?.textContent || ''"
            )
            == ""
        )


def test_late_invoice_reply_after_account_switch_does_not_restore_draft(
    live_app, i1_dataset
):
    """A stale authorized invoice response after account switch must not
    render draft data or home drafts, even when loadHome is triggered."""
    from app.auth.repo import create_user

    data = i1_dataset
    reader = "beta3_priv_reader_" + str(data["prefix"])
    password = "Synthetic-Beta3-Privacy-2026!"
    with Session(live_app[1]) as db:
        create_user(db, reader, password, role="warehouse_staff", is_owner=False)
        db.commit()

    invoice_path = "/invoices/" + str(data["draft"])
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        token = page.evaluate("localStorage.getItem('token')")
        witness = page.request.get(
            live_app[0] + invoice_path, headers={"Authorization": "Bearer " + token}
        )
        assert witness.status == 200
        invoice = witness.json()
        assert invoice["id"] == str(data["draft"])

        # Seed draft registry so home shows a row.
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
        expect(page.locator("#home-drafts tr")).to_have_count(1)

        # Hold a late authorized invoice reply.
        page.evaluate(
            """path => {
              const original = window.fetch;
              window.__bodyConsumed = false;
              window.fetch = function (...args) {
                return original.apply(window, args).then(response => {
                  if (new URL(args[0], location.href).pathname === path) {
                    const read = response.text.bind(response);
                    response.text = async function () {
                      const body = await read();
                      setTimeout(() => { window.__bodyConsumed = true; }, 0);
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

        def hold_authorized_reply(route):
            response = route.fetch()
            assert response.status == 200
            assert response.json()["id"] == invoice["id"]
            held.append((route, response))
            page.evaluate("window.__held = true")

        page.route("**" + invoice_path, hold_authorized_reply)
        row = page.locator("#home-drafts tr").filter(
            has=page.get_by_text(invoice["invoice_no"], exact=True)
        )
        row.get_by_role("button", name="Open", exact=True).click()
        wait_for_held(page, held)
        assert len(held) == 1

        # Logout, then account-switch to a restricted user.
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        page.locator("#login-username").fill(reader)
        page.locator("#login-password").fill(password)
        page.locator("#login-submit").click()
        expect(page.locator("#home-view")).to_be_visible()
        restricted_token = page.evaluate("localStorage.getItem('token')")
        assert restricted_token and restricted_token != token

        # Restricted user must not see prior user's drafts.
        assert (
            page.evaluate(
                "() => JSON.parse(localStorage.getItem('medsys.drafts.v1') || '[]').length"
            )
            == 0
        )
        expect(page.locator("#home-drafts")).not_to_contain_text(invoice["invoice_no"])

        # The restricted user must not be able to view the owner's invoice.
        assert (
            page.request.get(
                live_app[0] + invoice_path,
                headers={"Authorization": "Bearer " + restricted_token},
            ).status
            == 403
        )

        # Fulfill the stale response in the new session.
        route, response = held.pop()
        try:
            route.fulfill(response=response)
            page.wait_for_function("window.__bodyConsumed === true")
            # Home must remain clean; no prior-session draft data visible.
            expect(page.locator("#home-view")).to_be_visible()
            expect(page.locator("#draft-view")).to_be_hidden()
            expect(page.locator("#draft-view")).not_to_contain_text(
                invoice["invoice_no"]
            )
            expect(page.locator("#home-drafts")).not_to_contain_text(
                invoice["invoice_no"]
            )
            assert page.evaluate("localStorage.getItem('token')") == restricted_token
        finally:
            response.dispose()


@pytest.mark.parametrize("session_end", ["logout", "account_switch"])
def test_late_home_financial_reply_cannot_cross_session(
    live_app, i1_dataset, session_end
):
    """Hold loadHome's actual authorized balance body after its other reads finish."""
    from app.auth.repo import create_user

    data = i1_dataset
    reader = "home_privacy_" + data["prefix"] + "_" + session_end
    password = "Synthetic-Home-Privacy-2026!"
    with Session(live_app[1]) as db:
        create_user(db, reader, password, role="warehouse_staff", is_owner=False)
        db.commit()
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        page.emulate_media(reduced_motion="reduce")
        assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        expect(page.locator("#home-aging .aging-cell")).to_have_count(4)
        page.locator('#sidebar [data-view="balances"]').click()
        expect(page.locator("#balances-view")).to_be_visible()
        expect(
            page.locator(f'#ledger-customer option[value="{data["customer"]}"]')
        ).to_have_count(1)
        owner_token = page.evaluate("localStorage.getItem('token')")
        page.evaluate("""() => {
          const original = window.fetch;
          const calls = {};
          window.__homeRead = {};
          window.fetch = function (...args) {
            const path = new URL(args[0], location.href).pathname;
            const index = calls[path] = (calls[path] || 0) + 1;
            return original.apply(window, args).then(response => {
              if (index === 1 && response.status === 200 &&
                  ['/ar/balances', '/collections', '/inventory/stock'].includes(path)) {
                const read = response.text.bind(response);
                response.text = async function () {
                  const body = await read();
                  setTimeout(() => { window.__homeRead[path] = true; }, 0);
                  return body;
                };
              }
              return response;
            });
          };
        }""")
        held = []

        def hold_owner_home(route):
            if route.request.headers.get("authorization") != "Bearer " + owner_token:
                route.continue_()
                return
            response = route.fetch()
            assert response.status == 200
            assert any(
                row["customer_id"] == str(data["customer"]) for row in response.json()
            )
            held.append((route, response))
            page.evaluate("window.__homeBalanceHeld = true")

        page.route("**/ar/balances", hold_owner_home)
        page.locator('#sidebar [data-view="home"]').click()
        wait_for_held(page, held)
        page.wait_for_function(
            "window.__homeRead['/collections'] && window.__homeRead['/inventory/stock']"
        )
        assert len(held) == 1
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        if session_end == "account_switch":
            page.locator("#login-username").fill(reader)
            page.locator("#login-password").fill(password)
            page.locator("#login-submit").click()
            expect(page.locator("#home-view")).to_be_visible()
            token = page.evaluate("localStorage.getItem('token')")
            forbidden = page.request.get(
                live_app[0] + "/ar/balances",
                headers={"Authorization": "Bearer " + token},
            )
            assert forbidden.status == 403
        else:
            assert page.request.get(live_app[0] + "/ar/balances").status == 401
        route, response = held.pop()
        try:
            route.fulfill(response=response)
            page.wait_for_function("window.__homeRead['/ar/balances'] === true")
            expect(page.locator("#stat-ar")).to_have_text("—")
            expect(page.locator("#home-receipts")).not_to_contain_text(data["prefix"])
        finally:
            response.dispose()


def test_logout_erases_populated_invoice_editor_lines(live_app, i1_dataset):
    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        page.evaluate(
            "rows => localStorage.setItem('medsys.drafts.v1', JSON.stringify(rows))",
            [
                {
                    "id": str(data["draft"]),
                    "invoice_no": "EDITOR-" + data["prefix"],
                    "customer": "Synthetic customer",
                    "grand_total": "123.45",
                }
            ],
        )
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        page.locator("#home-drafts button").click()
        expect(page.locator("#draft-view")).to_be_visible()
        page.locator("#edit-draft").click()
        expect(page.locator("#invoice-view")).to_be_visible()
        expect(page.locator("#lines .line")).not_to_have_count(0)
        page.locator("#notes").fill("PRIVATE-EDITOR-" + data["prefix"])
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        expect(page.locator("#notes")).to_have_value("")
        expect(page.locator("#lines .line")).to_have_count(0)
