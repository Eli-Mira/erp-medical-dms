import copy
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from test_invoice_api import invoice_env  # noqa: F401

# Load the c9 module dynamically
c9_path = Path(__file__).resolve().parents[1] / "scripts" / "c9_synthetic_reconcile.py"
spec = importlib.util.spec_from_file_location("c9", c9_path)
c9 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(c9)

BASE_PACKET = {
    "branches": [
        {"code": "SYN-B1", "name_ar": "فرع 1", "name_en": "Syn Branch 1"}
    ],
    "territories": [
        {"code": "SYN-T1", "name_ar": "منطقة 1", "name_en": "Syn Territory 1"}
    ],
    "warehouses": [
        {
            "code": "SYN-W1",
            "name_ar": "مخزن 1",
            "name_en": "Syn Warehouse 1",
            "branch_code": "SYN-B1",
        }
    ],
    "products": [
        {
            "sku": "SYN-P1",
            "name_ar": "منتج 1",
            "name_en": "Prod 1",
            "public_price": "114.00",
            "vat_rate": "14.00",
        },
        {
            "sku": "SYN-P2",
            "name_ar": "منتج 2",
            "name_en": "Prod 2",
            "public_price": "50.00",
            "vat_rate": "0.00",
        },
    ],
    "customers": [
        {
            "code": "SYN-C1",
            "name_ar": "عميل 1",
            "name_en": "Cust 1",
            "branch_code": "SYN-B1",
            "territory_code": "SYN-T1",
        },
        {
            "code": "SYN-C2",
            "name_ar": "الفيوم قديم",
            "name_en": "Fayoum Old",
            "branch_code": "SYN-B1",
            "territory_code": "SYN-T1",
            "reconcile_only": True,
        },
    ],
    "opening_stock": [
        {"warehouse_code": "SYN-W1", "sku": "SYN-P1", "quantity": "100.000"},
        {
            "customer_code": "SYN-C1",
            "sku": "SYN-P2",
            "quantity": "25.000",
            "custody": "تحت التصريف",
        },
    ],
    "opening_ar": [
        {
            "customer_code": "SYN-C1",
            "amount": "1500.50",
            "store_balance": "1500.50",
            "grid_balance": "1500.50",
        },
        {
            "customer_code": "SYN-C2",
            "amount": "9999.00",
            "account_tag": "الفيوم قديم",
            "reconcile_only": True,
        },
    ],
}


def _count_master_customer(db, code: str) -> int:
    result = db.execute(
        text("SELECT COUNT(*) FROM master_data.master_customer WHERE code = :code"),
        {"code": code},
    )
    return int(result.scalar())


def test_vat_inclusive_public_price_extraction_eli_a4():
    # basic inclusive case
    assert c9.extract_net_and_vat_from_public_price(
        Decimal("114.00"), Decimal("14.00")
    ) == (Decimal("100.00"), Decimal("14.00"))

    # another inclusive case where net and vat must be derived
    assert c9.extract_net_and_vat_from_public_price(
        Decimal("100.00"), Decimal("14.00")
    ) == (Decimal("87.72"), Decimal("12.28"))

    # zero‑vat case – net equals public price
    assert c9.extract_net_and_vat_from_public_price(
        Decimal("50.00"), Decimal("0.00")
    ) == (Decimal("50.00"), Decimal("0.00"))


def test_dry_run_makes_zero_db_writes_and_classifies_consignment_and_reconcile_only(invoice_env):
    _, db, ids, _, _ = invoice_env

    res = c9.run_reconcile(
        db,
        copy.deepcopy(BASE_PACKET),
        official_codes={"SYN-C1", "SYN-C2", "SYN-P1", "SYN-P2"},
        cutoff_date=date(2026, 11, 21),
        apply=False,
        actor_user_id=str(ids["owner"]),
    )

    assert res["status"] == "DRY_RUN_OK"
    assert res["applied"] is False
    assert res["summary"] == {
        "active_ar_total": "1500.50",
        "reconcile_only_ar_total": "9999.00",
        "warehouse_stock_qty": "100.000",
        "customer_held_qty": "25.000",
    }

    # ensure nothing was persisted
    assert _count_master_customer(db, "SYN-C1") == 0


def test_store_vs_grid_conflict_rejected_with_zero_partial_writes(invoice_env):
    _, db, ids, _, _ = invoice_env

    pkt = copy.deepcopy(BASE_PACKET)
    # introduce a conflict between store and grid balances
    pkt["opening_ar"][0]["grid_balance"] = "1600.00"

    res = c9.run_reconcile(
        db,
        pkt,
        official_codes={"SYN-C1", "SYN-C2", "SYN-P1", "SYN-P2"},
        cutoff_date=date(2026, 11, 21),
        apply=True,
        actor_user_id=str(ids["owner"]),
    )

    assert res["status"] == "REJECTED_EXCEPTIONS"
    assert res["applied"] is False
    assert any(e.get("kind") == "store_grid_conflict" for e in res.get("exceptions", []))
    # no rows should have been written
    assert _count_master_customer(db, "SYN-C1") == 0


def test_unapproved_code_rejected_when_official_codes_provided(invoice_env):
    _, db, ids, _, _ = invoice_env

    res = c9.run_reconcile(
        db,
        copy.deepcopy(BASE_PACKET),
        official_codes={"SYN-C1", "SYN-C2", "SYN-P1"},  # SYN-P2 omitted on purpose
        cutoff_date=date(2026, 11, 21),
        apply=True,
        actor_user_id=str(ids["owner"]),
    )

    assert res["status"] == "REJECTED_EXCEPTIONS"
    assert any(e.get("kind") == "unapproved_code" for e in res.get("exceptions", []))


def test_apply_real_tables_reconciles_exact_decimal_and_is_idempotent(invoice_env):
    _, db, ids, _, _ = invoice_env

    # first application – should reconcile everything
    res = c9.run_reconcile(
        db,
        copy.deepcopy(BASE_PACKET),
        official_codes={"SYN-C1", "SYN-C2", "SYN-P1", "SYN-P2"},
        cutoff_date=date(2026, 11, 21),
        apply=True,
        actor_user_id=str(ids["owner"]),
    )

    assert res["status"] == "APPLIED_RECONCILED"
    assert res["reconciliation"]["ar_delta"] == "0.00"
    assert res["reconciliation"]["stock_delta"] == "0.000"

    def _ar_balance(code: str) -> Decimal:
        val = db.execute(
            text(
                "SELECT COALESCE(SUM(e.debit - e.credit), 0) "
                "FROM finance.ar_entry e "
                "JOIN master_data.master_customer c ON c.id = e.customer_id "
                "WHERE c.code = :code"
            ),
            {"code": code},
        ).scalar()
        return Decimal(str(val))

    def _stock_qty(wh: str, sku: str) -> Decimal:
        val = db.execute(
            text(
                "SELECT COALESCE(SUM(sb.quantity), 0) "
                "FROM inventory.stock_balance sb "
                "JOIN master_data.master_warehouse w ON w.id = sb.warehouse_id "
                "JOIN master_data.master_product p ON p.id = sb.product_id "
                "WHERE w.code = :wh AND p.sku = :sku"
            ),
            {"wh": wh, "sku": sku},
        ).scalar()
        return Decimal(str(val))

    def _held_qty(cust: str, sku: str) -> Decimal:
        val = db.execute(
            text(
                "SELECT COALESCE(SUM(h.quantity_on_hand), 0) "
                "FROM sales.customer_held_stock h "
                "JOIN master_data.master_customer c ON c.id = h.customer_id "
                "JOIN master_data.master_product p ON p.id = h.product_id "
                "WHERE c.code = :cust AND p.sku = :sku"
            ),
            {"cust": cust, "sku": sku},
        ).scalar()
        return Decimal(str(val))

    # verify AR balances
    assert _ar_balance("SYN-C1") == Decimal("1500.50")

    # reconcile-only customer should have no AR entries
    ar_entries_c2 = db.execute(
        text(
            "SELECT COUNT(*) FROM finance.ar_entry e "
            "JOIN master_data.master_customer c ON c.id = e.customer_id "
            "WHERE c.code = :code"
        ),
        {"code": "SYN-C2"},
    ).scalar()
    assert int(ar_entries_c2) == 0

    # verify stock balances
    assert _stock_qty("SYN-W1", "SYN-P1") == Decimal("100.000")

    # product SYN-P2 should have no warehouse stock rows (only held stock)
    stock_rows_p2 = db.execute(
        text(
            "SELECT COUNT(*) FROM inventory.stock_balance sb "
            "JOIN master_data.master_product p ON p.id = sb.product_id "
            "WHERE p.sku = :sku"
        ),
        {"sku": "SYN-P2"},
    ).scalar()
    assert int(stock_rows_p2) == 0

    # held stock for customer C1 / product P2
    assert _held_qty("SYN-C1", "SYN-P2") == Decimal("25.000")

    # base price for product SYN-P1 should be the net price
    base_price = db.execute(
        text(
            "SELECT base_price FROM master_data.master_product WHERE sku = :sku"
        ),
        {"sku": "SYN-P1"},
    ).scalar()
    assert Decimal(str(base_price)) == Decimal("100.00")

    # second run - should be idempotent
    res2 = c9.run_reconcile(
        db,
        copy.deepcopy(BASE_PACKET),
        official_codes={"SYN-C1", "SYN-C2", "SYN-P1", "SYN-P2"},
        cutoff_date=date(2026, 11, 21),
        apply=True,
        actor_user_id=str(ids["owner"]),
    )

    assert res2["inserted"] == {"stock": 0, "held": 0, "ar": 0}
    assert res2["skipped_idempotent"] == {"stock": 1, "held": 1, "ar": 1}

    # ensure totals unchanged after second run
    assert _ar_balance("SYN-C1") == Decimal("1500.50")
    assert _stock_qty("SYN-W1", "SYN-P1") == Decimal("100.000")
    assert _held_qty("SYN-C1", "SYN-P2") == Decimal("25.000")
