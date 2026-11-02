"""Real balance, statement and receipt history on the owned verifier only."""

import os
import re
from decimal import Decimal
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from sqlalchemy.engine import make_url
from test_customer_pwa import _browser_user
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414
from test_zz_i1_browser import i1_dataset as i1_dataset  # noqa: PLC0414


@pytest.fixture(scope="module", autouse=True)
def require_owned_database_before_module_seed():
    from app.config import POSTING_ENABLED
    from app.db import engine

    target = make_url(os.environ["DATABASE_URL"])
    assert os.environ.get("APP_ENV") == "test"
    assert target.host in {"localhost", "127.0.0.1", "::1"}
    assert re.fullmatch(r"dms_cycle_test_[0-9a-f]{32}", target.database or "")
    assert engine.url == target
    assert POSTING_ENABLED is False
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == target.database


@pytest.mark.parametrize(
    "lang,width", [("ar", 390), ("en", 1440)], ids=["ar390", "en1440"]
)
def test_balance_statement_and_receipts_match_persisted_records(
    live_app, i1_dataset, lang, width
):
    data = i1_dataset
    with data["engine"].connect() as witness:
        name = witness.scalar(
            text("SELECT name_ar FROM master_data.master_customer WHERE id=:id"),
            {"id": data["customer"]},
        )
        assert (
            witness.scalar(
                text(
                    "SELECT count(*) FROM master_data.master_customer WHERE name_ar=:name"
                ),
                {"name": name},
            )
            == 1
        )  # The visible name identifies exactly this synthetic customer.
        entries = (
            witness.execute(
                text(
                    "SELECT id,entry_type,debit,credit FROM finance.ar_entry "
                    "WHERE customer_id=:id ORDER BY entry_date,created_at"
                ),
                {"id": data["customer"]},
            )
            .mappings()
            .all()
        )
        assert [entry["entry_type"] for entry in entries] == ["invoice", "payment"]
        expected_balance = sum(
            (entry["debit"] - entry["credit"] for entry in entries), Decimal(0)
        )
        assert expected_balance == Decimal("128.00")
        receipt = (
            witness.execute(
                text(
                    "SELECT id,receipt_no,amount,status FROM finance.payment_receipt "
                    "WHERE invoice_id=:invoice"
                ),
                {"invoice": data["invoice"]},
            )
            .mappings()
            .one()
        )
        assert receipt["amount"] == Decimal("100.00")
        assert receipt["status"] == "Active"

    with _browser_user(live_app, lang=lang, width=width) as (page, _engine, _owner):

        def navigate(view):
            if (
                width < 1024
                and page.locator("#menu-toggle").get_attribute("aria-expanded")
                != "true"
            ):
                page.locator("#menu-toggle").click()
            page.locator(f'#sidebar [data-view="{view}"]').click()
            expect(page.locator(f"#{view}-view")).to_be_visible()

        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == "/ar/balances"
                and response.request.method == "GET"
            )
        ) as balances:
            navigate("balances")
        assert balances.value.status == 200
        selected = [
            row
            for row in balances.value.json()
            if row["customer_id"] == str(data["customer"])
        ]
        assert len(selected) == 1
        assert Decimal(selected[0]["balance"]) == expected_balance
        row = page.locator("#balance-rows tr").filter(
            has=page.get_by_text(name, exact=True)
        )
        expect(row).to_have_count(1)
        expect(row.locator("td").nth(2)).to_have_text("128.00")
        row.get_by_role("button").click()
        expect(page.locator("#ledger-customer")).to_have_value(str(data["customer"]))
        history = page.locator("#entry-rows tr")
        expect(history).to_have_count(2)
        expect(history.nth(0).locator("td").nth(2)).to_have_text(data["prefix"])
        expect(history.nth(0).locator("td").nth(4)).to_have_text("228.00")
        expect(history.nth(1).locator("td").nth(2)).to_have_text(receipt["receipt_no"])
        expect(history.nth(1).locator("td").nth(5)).to_have_text("100.00")
        expect(history.nth(1).locator("td").nth(6)).to_have_text("128.00")

        with page.expect_response(
            lambda response: (
                urlsplit(response.url).path == "/collections"
                and response.request.method == "GET"
            )
        ) as collections:
            navigate("collections")
        assert collections.value.status == 200
        matches = [
            item
            for item in collections.value.json()
            if item["id"] == str(receipt["id"])
        ]
        assert len(matches) == 1
        assert matches[0]["invoice_id"] == data["invoice"]
        assert Decimal(matches[0]["amount"]) == receipt["amount"]
        saved = page.locator("#receipt-rows tr").filter(
            has=page.get_by_text(receipt["receipt_no"], exact=True)
        )
        expect(saved).to_have_count(1)
        expect(saved).to_contain_text("100.00")
        expect(saved.locator("td").nth(2)).to_have_text(data["prefix"])

        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        navigate("collections")
        expect(saved).to_have_count(1)
        expect(saved).to_contain_text("100.00")
