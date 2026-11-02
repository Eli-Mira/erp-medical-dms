"""Real-browser draft editing contract; execute only in the isolated verifier."""

import os
import re
from decimal import Decimal
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.orm import Session
from test_customer_pwa import _browser_user
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


@pytest.fixture(autouse=True)
def require_disposable_financial_database():
    # This module is not admitted by conftest's financial-module allowlist.
    from app.config import POSTING_ENABLED
    from app.db import engine

    assert os.environ.get("APP_ENV") == "test", "Use the approved isolated verifier"
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", engine.url.database or "")
    assert POSTING_ENABLED is False, "Default posting must remain disabled"
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT current_database()")) == engine.url.database
        )


def test_browser_draft_notes_edit_survives_reopen_and_print(live_app):
    from app.sales.schemas import DraftUpdate

    prefix = "L2-" + uuid4().hex[:16]
    ids = {
        key: uuid4()
        for key in ("branch", "territory", "warehouse", "customer", "product")
    }
    original_notes = "Synthetic draft note before editing"
    edited_notes = "Synthetic draft note persisted after editing"

    with _browser_user(live_app, lang="en", width=1440) as (page, engine, owner):
        with Session(engine) as db:
            assert db.scalar(text("SELECT current_database()")) == engine.url.database
            db.execute(
                text(
                    "INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,:name)"
                ),
                {"id": ids["branch"], "code": prefix, "name": prefix},
            )
            db.execute(
                text(
                    "INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,:name)"
                ),
                {"id": ids["territory"], "code": prefix, "name": prefix},
            )
            db.execute(
                text(
                    "INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:branch,:code,:name)"
                ),
                {
                    "id": ids["warehouse"],
                    "branch": ids["branch"],
                    "code": prefix,
                    "name": prefix,
                },
            )
            db.execute(
                text(
                    "INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,:name,:branch,:territory)"
                ),
                {
                    "id": ids["customer"],
                    "code": prefix,
                    "name": prefix,
                    "branch": ids["branch"],
                    "territory": ids["territory"],
                },
            )
            db.execute(
                text(
                    "INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,:name,114,14)"
                ),
                {"id": ids["product"], "sku": prefix, "name": prefix},
            )
            db.commit()

        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        page.locator('#sidebar [data-view="invoice"]').click()
        expect(page.locator("#invoice-view")).to_be_visible()
        page.get_by_test_id("invoice-no").fill(prefix)
        expect(
            page.locator(f'#customer option[value="{ids["customer"]}"]')
        ).to_have_count(1)
        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == "/master/warehouses"
                and response.request.method == "GET"
            )
        ) as warehouses:
            page.get_by_test_id("customer").select_option(str(ids["customer"]))
        assert warehouses.value.status == 200
        page.get_by_test_id("warehouse").select_option(str(ids["warehouse"]))
        page.locator('#lines select[data-role="product"]').select_option(
            str(ids["product"])
        )
        page.locator('#lines input[data-role="qty"]').fill("2")
        page.get_by_test_id("notes").fill(original_notes)
        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == "/invoices"
                and response.request.method == "POST"
            )
        ) as created:
            page.get_by_test_id("save-draft").click()
        assert created.value.status == 201, created.value.text()
        invoice = created.value.json()
        invoice_path = "/invoices/" + invoice["id"]
        assert invoice["posting_status"] == "Draft"
        assert invoice["notes"] == original_notes
        assert Decimal(invoice["grand_total"]) == Decimal("228.00")
        expect(page.locator("#draft-view")).to_be_visible()

        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == invoice_path + "/post"
                and response.request.method == "POST"
            )
        ) as refused:
            page.get_by_test_id("post-draft").click()
        assert refused.value.status == 409
        assert "disabled" in refused.value.json()["detail"].lower()
        expect(page.locator("#draft-error")).to_be_visible()

        def reopen_from_server():
            page.reload(wait_until="domcontentloaded")
            expect(page.locator("#home-view")).to_be_visible()
            row = page.locator("#home-drafts tr").filter(
                has=page.get_by_text(prefix, exact=True)
            )
            expect(row).to_have_count(1)
            with page.expect_response(
                lambda response: (
                    urlsplit(response.url).path == invoice_path
                    and response.request.method == "GET"
                )
            ) as reopened:
                row.get_by_role("button", name="Open", exact=True).click()
            assert reopened.value.status == 200
            expect(page.locator("#draft-view")).to_be_visible()
            expect(page.locator("#draft-no")).to_have_text(prefix)
            return reopened.value.json()

        assert reopen_from_server() == invoice
        edit = page.locator("#draft-view").get_by_role(
            "button", name="Edit draft", exact=True
        )
        expect(
            edit, "A reopened Draft must expose an enabled Edit draft action"
        ).to_be_visible()
        expect(edit).to_be_enabled()
        edit.click()
        expect(page.get_by_test_id("notes")).to_be_visible()
        expect(page.get_by_test_id("notes")).to_have_value(original_notes)
        page.get_by_test_id("notes").fill(edited_notes)
        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == invoice_path
                and response.request.method == "PUT"
            )
        ) as updated:
            page.get_by_test_id("save-draft").click()
        assert updated.value.status == 200, updated.value.text()
        sent = DraftUpdate.model_validate(updated.value.request.post_data_json)
        assert sent.version == invoice["version"]
        assert sent.notes == edited_notes
        saved = updated.value.json()
        assert saved["id"] == invoice["id"]
        assert saved["version"] == invoice["version"] + 1
        assert saved["notes"] == edited_notes
        assert saved["posting_status"] == "Draft"
        for key in (
            "invoice_no",
            "customer_id",
            "branch_id",
            "territory_id",
            "warehouse_id",
            "invoice_date",
            "grand_total",
            "total_net",
            "vat_amount",
        ):
            assert saved[key] == invoice[key], key
        assert reopen_from_server() == saved

        # Observe the native print lifecycle without replacing window.print or the DOM.
        page.evaluate(
            "window.addEventListener('beforeprint', () => { window.__lane2Printed = true; }, {once: true})"
        )
        page.get_by_test_id("print-invoice").click()
        page.wait_for_function("window.__lane2Printed === true")
        page.emulate_media(media="print")
        expect(page.locator("#draft-view")).to_be_visible()
        expect(page.locator("#draft-no")).to_have_text(prefix)
        expect(page.locator("#draft-grand")).to_have_text("228.00")
        expect(
            page.locator("#draft-view").get_by_text(edited_notes, exact=True)
        ).to_be_visible()
        expect(page.locator("#draft-lines tr")).to_have_count(1)
        expect(page.locator("#draft-lines tr td").nth(1)).to_have_text("2")
        pdf = page.pdf(print_background=True)
        assert pdf.startswith(b"%PDF-")
        page.emulate_media(media="screen")

        with engine.connect() as witness:
            stored = (
                witness.execute(
                    text(
                        "SELECT notes,version,posting_status FROM sales.sales_invoice WHERE id=:id"
                    ),
                    {"id": invoice["id"]},
                )
                .mappings()
                .one()
            )
            assert dict(stored) == {
                "notes": edited_notes,
                "version": saved["version"],
                "posting_status": "Draft",
            }
            audit = (
                witness.execute(
                    text(
                        "SELECT actor_user_id,old_values,new_values FROM audit.audit_log WHERE entity_type='sales_invoice' AND entity_id=:id AND action='modified'"
                    ),
                    {"id": invoice["id"]},
                )
                .mappings()
                .one()
            )
            assert audit["actor_user_id"] == owner
            assert audit["old_values"]["notes"] == original_notes
            assert audit["new_values"]["notes"] == edited_notes
            assert (
                witness.scalar(
                    text(
                        "SELECT count(*) FROM inventory.stock_movement WHERE source_id=:id"
                    ),
                    {"id": invoice["id"]},
                )
                == 0
            )
            assert (
                witness.scalar(
                    text("SELECT count(*) FROM finance.ar_entry WHERE invoice_id=:id"),
                    {"id": invoice["id"]},
                )
                == 0
            )
