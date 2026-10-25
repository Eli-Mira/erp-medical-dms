"""Bounded synthetic directory-size reproduction of the retained workflow."""

from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from test_customer_pwa import _browser_user, customer_page, references
from test_customer_pwa import (
    test_owner_customer_workflow_persists_after_refresh as owner_workflow,
)
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


@pytest.mark.parametrize("width", [1440, 390])
def test_contact_directory_size_reproduction(live_app, width, request):
    branch, territory = references(live_app[1])
    prefix = "PROBE-" + uuid4().hex[:12]
    with live_app[1].begin() as db:
        db.execute(
            text(
                "INSERT INTO master_data.master_customer(code,name_ar,branch_id,territory_id) SELECT :prefix || n, 'عميل حجم دليل ' || n, :b, :t FROM generate_series(1, 200) n"
            ),
            {"prefix": prefix, "b": branch, "t": territory},
        )
    try:
        with _browser_user(live_app, width=width) as (page, _engine, _owner):
            customer_page(page, width)
            rows = page.locator("#customer-rows tr[data-customer-id]")
            expect(rows).to_have_count(50)
            first = rows.evaluate_all("rows => rows.map(r => r.dataset.customerId)")
            expect(page.locator("#customer-prev")).to_be_disabled()
            page.locator("#customer-next").click()
            expect(page.locator("#customer-page-status")).to_contain_text("51–100")
            second = rows.evaluate_all("rows => rows.map(r => r.dataset.customerId)")
            assert len(second) == 50 and not set(first).intersection(second)
            assert page.locator("#customer option").count() >= 200
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#home-view")).to_be_visible()
            customer_page(page, width)
            expect(page.locator("#customer-page-status")).to_contain_text("51–100")
            assert (
                rows.evaluate_all("rows => rows.map(r => r.dataset.customerId)")
                == second
            )
            page.locator("#customer-prev").click()
            assert (
                rows.evaluate_all("rows => rows.map(r => r.dataset.customerId)")
                == first
            )
        owner_workflow(live_app, "ar", width, request)
    finally:
        with live_app[1].begin() as db:
            db.execute(
                text(
                    "DELETE FROM master_data.master_customer WHERE branch_id=:b AND territory_id=:t AND left(code,length(:prefix))=:prefix"
                ),
                {"b": branch, "t": territory, "prefix": prefix},
            )
        print(
            "CONTAINER_MEMORY_EVENTS", Path("/sys/fs/cgroup/memory.events").read_text()
        )
        print("CONTAINER_MEMORY_PEAK", Path("/sys/fs/cgroup/memory.peak").read_text())
        print("CONTAINER_PIDS", Path("/sys/fs/cgroup/pids.current").read_text())
        counters = dict(
            line.split()
            for line in Path("/sys/fs/cgroup/memory.events").read_text().splitlines()
        )
        assert int(counters["oom_kill"]) == 0
