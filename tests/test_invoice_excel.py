"""Real-Excel reconciliation tests: invoke actual app calc (not re-derived
formulas) against cached values from the source .xlsx workbooks.

Scope: complete numeric rows in TWO named transaction sheets, not all sales
workbooks. Every numeric row is tested with a strict one-piastre threshold;
no row is excluded because its result disagrees. Historical return rows are
checked arithmetically, not accepted as invoice API input.

VAT reconciliation against Excel is NOT claimed — the source workbooks carry
no VAT column; VAT (rate=14%) is an app-level extraction from VAT-inclusive
prices and is only verified internally (total_net + vat_amount == grand_total).
"""
import pytest
from pathlib import Path
from decimal import Decimal
import openpyxl
from app.sales.calc import line_calc, invoice_totals

ROOT = Path(__file__).resolve().parents[1]
SALES_WORKBOOKS = [ROOT / name for name in ("مبيعات 6 اكتوبر 2026.xlsx", "مبيعات الدقهليه 2026.xlsx")]
pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in SALES_WORKBOOKS),
    reason="source sales workbooks absent (git-ignored)",
)
# Float cache noise below one piastre is tolerated; larger differences fail.
TOL_LT = Decimal("0.01")


def _txn_sheets(ws):
    """True if ws looks like a per-warehouse transaction sheet."""
    try:
        hdr = next(ws.iter_rows(min_row=1, max_row=1, min_col=2, max_col=6, values_only=True))
    except StopIteration:
        return False
    if ws.title not in {"مخزن الزهراء اكتوبر", "مخزن السحيلى المنزلة"}:
        return False
    names = [str(h).strip().lower() if h else "" for h in hdr]
    return (
        names[0] == "quantity"
        and names[1] == "price"
        and "خصم" in names[2]
        and "net" in names[3]
        and names[4] == "total"
    )


def test_line_total_matches_excel_cached_value():
    """Compare app net price AND line total against every numeric source row."""
    checked = 0
    mismatches = []
    for f in SALES_WORKBOOKS:
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            if not _txn_sheets(ws):
                continue
            assert ws.max_row == (3916 if ws.title == "مخزن الزهراء اكتوبر" else 4440)
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=2, max_col=6, values_only=True):
                qty_v, price_v, disc_v, _net_v, total_excel = (
                    row[0], row[1], row[2], row[3], row[4]
                )
                if not all(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in (qty_v, price_v, disc_v, _net_v, total_excel)
                ):
                    continue
                if qty_v is None or price_v is None or disc_v is None:
                    continue
                qty = Decimal(str(qty_v))
                price = Decimal(str(price_v))
                # Excel D column stores discount as a fraction (0.30 = 30%); calc
                # expects a percentage.
                disc_pct = Decimal(str(disc_v)) * Decimal("100")
                app_net, lt, _ = line_calc(qty, price, disc_pct, Decimal("14"))
                diff = abs(lt - Decimal(str(total_excel)))
                if diff >= TOL_LT or abs(app_net - Decimal(str(_net_v))) >= TOL_LT:
                    mismatches.append((f.name, sheet, str(qty), str(price), str(total_excel), str(lt)))
                checked += 1
        wb.close()
    # Freeze the observed coverage; missing/added rows require explicit review.
    assert checked == 133, checked
    assert not mismatches, mismatches


def test_invoice_totals_invariant_on_real_rows():
    """Aggregate rows from transaction sheets across the first two workbooks
    and assert the reconciliation invariant holds exactly on the app's output.
    """
    lines = []
    wb_count = 0
    for f in SALES_WORKBOOKS[:2]:
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        for sname in wb.sheetnames:
            ws = wb[sname]
            if not _txn_sheets(ws):
                continue
            assert ws.max_row == (3916 if ws.title == "مخزن الزهراء اكتوبر" else 4440)
            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=2, max_col=6, values_only=True):
                qty_v, price_v, disc_v, _, _ = row[0], row[1], row[2], row[3], row[4]
                if not all(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    for v in (qty_v, price_v, disc_v)
                ):
                    continue
                if qty_v is None or price_v is None or disc_v is None:
                    continue
                lines.append(
                    (
                        Decimal(str(qty_v)),
                        Decimal(str(price_v)),
                        Decimal(str(disc_v)) * 100,
                        Decimal("14"),
                    )
                )
            wb_count += 1
            if wb_count >= 2:
                wb.close()
                break
        else:
            wb.close()
            continue
        break
    assert len(lines) >= 50, f"need at least 50 lines, found {len(lines)}"
    t = invoice_totals(lines)
    assert t["total_before_discount"] - t["total_discount"] == t["grand_total"]


def test_vat_invariant_holds_but_not_excel_reconciled():
    """App-level VAT extraction: total_net + vat_amount == grand_total.
    No assertion against Excel — the workbooks carry no VAT column, so
    Excel-based VAT reconciliation is intentionally NOT claimed.

    shortcut: VAT is not Excel-verifiable because source workbooks lack a VAT
    breakdown column; only the app's half-up extraction is asserted here.
    """
    f = SALES_WORKBOOKS[0]
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    txn = None
    for sname in wb.sheetnames:
        ws = wb[sname]
        if _txn_sheets(ws):
            txn = ws
            break
    assert txn is not None
    lines = []
    for row in txn.iter_rows(min_row=2, max_row=500, min_col=2, max_col=6, values_only=True):
        qty_v, price_v, disc_v, _, _ = row[0], row[1], row[2], row[3], row[4]
        if not all(
            isinstance(v, (int, float)) and not isinstance(v, bool)
            for v in (qty_v, price_v, disc_v)
        ):
            continue
        if qty_v is None or price_v is None or disc_v is None:
            continue
        lines.append(
            (
                Decimal(str(qty_v)),
                Decimal(str(price_v)),
                Decimal(str(disc_v)) * 100,
                Decimal("14"),
            )
        )
    wb.close()
    assert len(lines) >= 50, len(lines)
    t = invoice_totals(lines)
    assert t["total_net"] + t["vat_amount"] == t["grand_total"]
