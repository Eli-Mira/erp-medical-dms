"""Late financial UI replies must not restore an ended authenticated session."""

from decimal import Decimal
from secrets import token_urlsafe
from urllib.parse import urlsplit
from uuid import uuid4

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


def _observe_body_consumption(page, url, method):
    # api() reads text; the next task runs after saveDraft/openSavedDraft microtasks.
    page.evaluate(
        """({url, method}) => {
          const original = window.fetch;
          window.__invoiceBodyConsumed = false;
          document.documentElement.__invoiceBodyConsumed = false;
          window.fetch = function (input, init) {
            const target = new URL(input instanceof Request ? input.url : input,
                                   location.href).href;
            const verb = (init && init.method) ||
                         (input instanceof Request ? input.method : 'GET');
            return original.apply(this, arguments).then(response => {
              if (target === url && verb.toUpperCase() === method) {
                const read = response.text.bind(response);
                response.text = async function () {
                  const body = await read();
                  setTimeout(() => {
                    window.__invoiceBodyConsumed = true;
                    document.documentElement.__invoiceBodyConsumed = true;
                  }, 0);
                  return body;
                };
              }
              return response;
            });
          };
        }""",
        {"url": url, "method": method},
    )


def _hold_authorized_reply(page, url, method, status, check_body):
    """Hold only the exact method AND absolute URL; forward everything else."""
    held, forwarded = [], []

    def intercept(route):
        request = route.request
        if request.url != url or request.method != method:
            forwarded.append((request.method, request.url))
            return route.continue_()
        response = route.fetch()
        assert response.status == status
        check_body(response.json())
        held.append((route, response))

    page.route("**/*", intercept)
    return held, forwarded


def test_late_saved_invoice_reply_does_not_replace_login(live_app, i1_dataset):
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
        row = page.locator("#home-drafts tr").filter(
            has=page.get_by_text(invoice["invoice_no"], exact=True)
        )
        expect(row).to_have_count(1)
        url = live_app[0] + invoice_path
        _observe_body_consumption(page, url, "GET")

        def check_invoice(body):
            assert body["id"] == invoice["id"]

        held, _forwarded = _hold_authorized_reply(page, url, "GET", 200, check_invoice)
        row.get_by_role("button", name="Open", exact=True).click()
        wait_for_held(page, held)
        assert len(held) == 1
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        assert page.request.get(live_app[0] + invoice_path).status == 401
        route, response = held.pop()
        try:
            route.fulfill(response=response)
            expect(page.locator("html")).to_have_js_property("__invoiceBodyConsumed", True, timeout=10000)
            expect(page.locator("#login-view")).to_be_visible()
            expect(page.locator("#draft-view")).to_be_hidden()
            assert page.evaluate("localStorage.getItem('token')") is None
            print("ASSERTION_REACHED financial_session saved_invoice_GET late_reply_privacy", flush=True)
        finally:
            response.dispose()


@pytest.mark.parametrize("session_end", ["logout", "account_change"])
def test_late_created_invoice_post_reply_cannot_restore_financial_data(
    live_app, i1_dataset, session_end
):
    from app.auth.repo import create_user

    data = i1_dataset
    canary = "LATE-POST-" + uuid4().hex[:16]
    notes = "Synthetic financial privacy canary " + uuid4().hex
    url = live_app[0] + "/invoices"
    with _browser_user(live_app, lang="en", width=1440) as (page, engine, _owner):
        page.locator('#sidebar [data-view="invoice"]').click()
        expect(page.locator("#invoice-view")).to_be_visible()
        customer = str(data["customer"])
        warehouse = str(data["warehouse"])
        product = str(data["product"])
        expect(page.locator(f'#customer option[value="{customer}"]')).to_have_count(1)
        with page.expect_response(
            lambda r: urlsplit(r.url).path == "/master/warehouses"
            and r.request.method == "GET"
        ) as warehouses:
            page.locator("#customer").select_option(customer)
        assert warehouses.value.status == 200
        expect(page.locator(f'#warehouse option[value="{warehouse}"]')).to_have_count(1)
        page.locator("#warehouse").select_option(warehouse)
        page.locator("#invoice-no").fill(canary)
        page.locator("#invoice-date").fill(str(data["today"]))
        page.locator("#notes").fill(notes)
        page.locator('[id^="line-product-"]').first.select_option(product)
        page.locator('[id^="line-qty-"]').first.fill("2")
        _observe_body_consumption(page, url, "POST")
        created = {}

        def check_created(body):
            assert body["invoice_no"] == canary
            assert body["notes"] == notes
            assert body["posting_status"] == "Draft"
            assert body["customer_id"] == customer
            assert body["warehouse_id"] == warehouse
            assert len(body["lines"]) == 1
            assert body["lines"][0]["product_id"] == product
            assert Decimal(body["grand_total"]) == Decimal("228.00")
            assert body["id"]
            created.update(body)

        held, forwarded = _hold_authorized_reply(page, url, "POST", 201, check_created)
        page.locator("#save-draft").click()
        wait_for_held(page, held)
        assert len(held) == 1 and created
        expect(page.locator("#save-draft")).to_be_disabled()
        assert not page.evaluate("window.__invoiceBodyConsumed")

        # Browser fetches traverse the actual route helper, unlike page.request.
        # Same-path GET and unrelated POST must complete while creation stays held.
        controls = page.evaluate(
            """async () => {
              const headers = {Authorization: 'Bearer ' + localStorage.getItem('token')};
              const read = await fetch('/invoices', {headers});
              await read.text();
              const unrelated = await fetch('/auth/logout', {method: 'POST'});
              await unrelated.text();
              return {read: read.status, unrelated: unrelated.status};
            }"""
        )
        assert controls == {"read": 200, "unrelated": 401}
        assert ("GET", url) in forwarded
        assert ("POST", live_app[0] + "/auth/logout") in forwarded
        assert len(held) == 1
        assert not page.evaluate("window.__invoiceBodyConsumed")
        old_token = page.evaluate("localStorage.getItem('token')")
        witness = page.request.get(
            url + "/" + created["id"],
            headers={"Authorization": "Bearer " + old_token},
        )
        assert witness.status == 200 and witness.json()["notes"] == notes

        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        final_token = None
        if session_end == "account_change":
            username, password = "late_post_" + uuid4().hex[:12], token_urlsafe(24)
            other_branch = str(uuid4())
            with Session(engine) as db:
                # A legitimate different-branch account cannot read A's draft.
                db.execute(
                    text("INSERT INTO master_data.master_branch(id,code,name_ar,name_en) VALUES (:id,:code,:name,:name)"),
                    {"id": other_branch, "code": "LATE-BR-" + uuid4().hex[:12], "name": "Synthetic privacy branch"},
                )
                create_user(db, username, password, role="read_only_auditor", is_owner=False)
                grant = db.execute(
                    text("INSERT INTO platform.user_branch(user_id,branch_id) SELECT id,:branch FROM platform.platform_user WHERE username=:username"),
                    {"branch": other_branch, "username": username},
                )
                assert grant.rowcount == 1
                db.commit()
            page.locator("#login-username").fill(username)
            page.locator("#login-password").fill(password)
            page.locator("#login-submit").click()
            expect(page.locator("#home-view")).to_be_visible()
            final_token = page.evaluate("localStorage.getItem('token')")
            assert final_token and final_token != old_token
            restricted = page.request.get(
                url + "/" + created["id"],
                headers={"Authorization": "Bearer " + final_token},
            )
            assert restricted.status == 404
            assert restricted.json() == {"detail": "Invoice or reference not found"}
        else:
            assert page.request.get(url + "/" + created["id"]).status == 401

        route, response = held.pop()
        try:
            route.fulfill(response=response)
            expect(page.locator("html")).to_have_js_property("__invoiceBodyConsumed", True, timeout=10000)
            expect(page.locator("#draft-view")).to_be_hidden()
            expect(page.locator("#home-view" if final_token else "#login-view")).to_be_visible()
            assert page.evaluate("localStorage.getItem('token')") == final_token
            # Check retained hidden DOM, editor values AND local shortcut storage.
            assert page.evaluate(
                """({canary, notes, id}) => {
                  const draft = document.querySelector('#draft-view');
                  const form = document.querySelector('#invoice-form');
                  const registry = localStorage.getItem('medsys.drafts.v1') || '';
                  return !draft.textContent.includes(canary) &&
                    !draft.textContent.includes(notes) &&
                    ['draft-no', 'draft-notes', 'draft-customer', 'draft-warehouse',
                     'draft-date', 'draft-status', 'draft-before', 'draft-discount',
                     'draft-net', 'draft-vat', 'draft-grand'].every(key =>
                       document.getElementById(key).textContent === '') &&
                    document.querySelector('#draft-lines').children.length === 0 &&
                    !Array.from(form.elements).some(e => e.value === canary || e.value === notes) &&
                    !registry.includes(id) && !registry.includes(canary) &&
                    !document.querySelector('#home-drafts').textContent.includes(canary);
                }""",
                {"canary": canary, "notes": notes, "id": created["id"]},
            )
            print(
                "ASSERTION_REACHED financial_session create_invoice_POST late_reply_privacy " + session_end,
                flush=True,
            )
        finally:
            response.dispose()
