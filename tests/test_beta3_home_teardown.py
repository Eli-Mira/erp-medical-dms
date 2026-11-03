"""Populated Home teardown and real queued KPI callbacks at session end."""

import pytest
from browser_readiness import wait_for_held
from playwright.sync_api import expect
from sqlalchemy.orm import Session
from test_customer_pwa import _browser_user
from test_lane2_balance_history_browser import (
    require_owned_database_before_module_seed as require_owned_database_before_module_seed,  # noqa: PLC0414
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414
from test_zz_i1_browser import i1_dataset as i1_dataset  # noqa: PLC0414


@pytest.mark.parametrize(
    "next_account", [False, True], ids=["logout", "account_switch"]
)
def test_populated_home_finance_is_erased_at_logout(live_app, i1_dataset, next_account):
    from app.auth.repo import create_user

    data = i1_dataset
    reader = "home_teardown_" + data["prefix"] + str(next_account)
    password = "Synthetic-Home-Teardown-2026!"
    with Session(live_app[1]) as db:
        create_user(db, reader, password, role="warehouse_staff", is_owner=False)
        db.commit()
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        page.emulate_media(reduced_motion="reduce")
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        expect(page.locator("#stat-ar")).to_have_text("128.00")
        expect(page.locator("#home-receipts")).to_contain_text(data["prefix"])
        expect(page.locator("#home-aging .aging-cell")).to_have_count(4)
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        expect(page.locator("#home-receipts")).to_have_text("")
        expect(page.locator("#home-aging")).to_have_text("")
        for name in ["ar", "stock", "receipts", "sales"]:
            expect(page.locator("#stat-" + name)).to_have_text("—")
            expect(page.locator("#stat-" + name + "-sub")).to_have_text("")
        if next_account:
            page.locator("#login-username").fill(reader)
            page.locator("#login-password").fill(password)
            page.locator("#login-submit").click()
            expect(page.locator("#home-view")).to_be_visible()
            token = page.evaluate("localStorage.getItem('token')")
            assert (
                page.request.get(
                    live_app[0] + "/ar/balances",
                    headers={"Authorization": "Bearer " + token},
                ).status
                == 403
            )
            expect(page.locator("#home-receipts")).not_to_contain_text(data["prefix"])
            expect(page.locator("#stat-ar")).to_have_text("—")


def test_queued_real_home_counters_cannot_restore_logged_out_values(
    live_app, i1_dataset
):
    data = i1_dataset
    with _browser_user(live_app, lang="en", width=1440) as (page, _engine, _owner):
        page.emulate_media(reduced_motion="reduce")
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#stat-ar")).to_have_text("128.00")
        expect(page.locator("#home-receipts")).to_contain_text(data["prefix"])
        page.emulate_media(reduced_motion="no-preference")
        assert not page.evaluate(
            "matchMedia('(prefers-reduced-motion: reduce)').matches"
        )
        page.evaluate("""() => {
          window.__heldHomeFrames = [];
          window.requestAnimationFrame = callback => {
            window.__heldHomeFrames.push({callback, queuedAt: performance.now()});
            return window.__heldHomeFrames.length;
          };
        }""")
        page.locator('#sidebar [data-view="balances"]').click()
        expect(page.locator("#balances-view")).to_be_visible()
        page.locator('#sidebar [data-view="home"]').click()
        wait_for_held(page, "window.__heldHomeFrames.length", count=4)
        expect(page.locator("#home-receipts")).to_contain_text(data["prefix"])
        page.locator("#logout").click()
        expect(page.locator("#login-view")).to_be_visible()
        # Execute the app's actual captured callbacks after teardown, not a mocked counter.
        executed = page.evaluate("""() => {
          const pending = window.__heldHomeFrames.splice(0);
          pending.forEach(frame => frame.callback(frame.queuedAt + 10000));
          return pending.length;
        }""")
        assert executed >= 4
        for name in ["ar", "stock", "receipts", "sales"]:
            expect(page.locator("#stat-" + name)).to_have_text("—")
