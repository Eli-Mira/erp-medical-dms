"""Reconciliation tests (Option C, rule 1): verify documented business rules
against the ACTUAL source workbooks.

The 7 source .xlsx files are READ-ONLY inputs and are git-ignored (D25), so
these tests SKIP when the workbooks are not present (e.g. CI). Locally they run
against the real data. Each test encodes a rule from
docs/MIGRATION_RECONCILIATION_PLAN.md or docs/EXCEL_TO_SYSTEM_MAPPING.md and
checks it against real cell values.

Rules that do NOT hold are NOT asserted here (a failing test is not a
reconciliation result) - they are reported in docs/PRE_CODING_VERIFICATION.md.
"""
import hashlib
import re
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {p.name: p for p in ROOT.glob("*.xlsx")}
SALES_6OCT = "مبيعات 6 اكتوبر 2026.xlsx"
SALES_DAK = "مبيعات الدقهليه 2026.xlsx"
FINANCE = "الميزانية العمومية 2026.xlsx"
TOL = 0.01  # EGP rounding tolerance

pytestmark = pytest.mark.skipif(
    len(SOURCES) < 7, reason="source workbooks absent (git-ignored, D25)"
)


def _sheet(name, sheet):
    wb = openpyxl.load_workbook(SOURCES[name], read_only=True, data_only=True)
    return wb, wb[sheet]


def _nums(*vals):
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals)


def test_sources_match_frozen_hashes():
    # D25 source integrity: every workbook matches SOURCE_HASHES.txt.
    baseline = {}
    for line in (ROOT / "SOURCE_HASHES.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([0-9a-f]{64})\s+(.+)$", line.strip())
        if m:
            baseline[m.group(2).strip()] = m.group(1)
    assert len(baseline) == 7, baseline
    for name, digest in baseline.items():
        assert hashlib.sha256(SOURCES[name].read_bytes()).hexdigest() == digest, name


def test_sources_are_full_size_real_workbooks():
    # Guard (Eli): reconciliation must run against the REAL source workbooks,
    # not sample/empty fixtures. Asserts the actual sheets are full-size.
    wb = openpyxl.load_workbook(SOURCES[FINANCE], read_only=True)
    ws = wb["العملاء"]
    assert ws.max_row >= 40 and ws.max_column >= 700, (ws.max_row, ws.max_column)
    wb.close()
    wb = openpyxl.load_workbook(SOURCES[SALES_6OCT], read_only=True)
    ws = wb["مخزن الزهراء اكتوبر"]
    assert ws.max_row >= 3000, ws.max_row
    wb.close()


def test_ar_row1_total_is_2_200_000():
    # MIGRATION_RECONCILIATION_PLAN + D23: AR ledger row-1 total = 2,200,000
    wb, ws = _sheet(FINANCE, "العملاء")
    row1 = next(ws.iter_rows(min_row=1, max_row=1, max_col=2, values_only=True))
    assert row1[0] == "العملاء"
    assert float(row1[1]) == 2_200_000.0
    wb.close()


def test_ar_balance_opening_and_running():
    # D23: opening D = E - F ; subsequent D = prev + E - F
    # (customer block 1 occupies cols D,E,F = الرصيد, مدين, دائن; header r3, data r4+)
    wb, ws = _sheet(FINANCE, "العملاء")
    prev = None
    checked = 0
    for bal, deb, cred in ws.iter_rows(min_row=4, max_row=16, min_col=4, max_col=6, values_only=True):
        if bal is None:
            continue
        deb, cred = deb or 0, cred or 0
        expect = (deb - cred) if prev is None else (prev + deb - cred)
        assert abs(bal - expect) < TOL, (prev, bal, deb, cred)
        prev, checked = bal, checked + 1
    assert checked >= 5, checked
    wb.close()


def test_net_price_rule_in_transaction_sheet():
    # EXCEL_TO_SYSTEM_MAPPING: E = C * (1 - D)   (C=price, D=الخصم, E=Net price)
    wb, ws = _sheet(SALES_6OCT, "مخزن الزهراء اكتوبر")
    checked = 0
    for price, disc, net in ws.iter_rows(min_row=2, max_row=300, min_col=3, max_col=5, values_only=True):
        if not _nums(price, disc, net):
            continue
        assert abs(net - price * (1 - disc)) < TOL, (price, disc, net)
        checked += 1
    assert checked >= 20, checked
    wb.close()


def test_net_price_rule_holds_in_second_branch():
    # same rule, Dakahlia branch -> cross-branch consistency
    wb, ws = _sheet(SALES_DAK, "مخزن السحيلى المنزلة")
    checked = 0
    for price, disc, net in ws.iter_rows(min_row=2, max_row=300, min_col=3, max_col=5, values_only=True):
        if not _nums(price, disc, net):
            continue
        assert abs(net - price * (1 - disc)) < TOL, (price, disc, net)
        checked += 1
    assert checked >= 10, checked
    wb.close()


def test_line_total_is_qty_times_net():
    # transaction sheet: total (F) = quantity (B) * net price (E)
    wb, ws = _sheet(SALES_6OCT, "مخزن الزهراء اكتوبر")
    checked = 0
    for qty, _price, _disc, net, total in ws.iter_rows(
        min_row=2, max_row=300, min_col=2, max_col=6, values_only=True
    ):
        if not _nums(qty, net, total):
            continue
        assert abs(total - qty * net) < TOL, (qty, net, total)
        checked += 1
    assert checked >= 5, checked
    wb.close()


def test_hq_rollup_balance_is_sales_minus_collection():
    # Reconcile EVERY numeric named row, including zero-sales rows. The known
    # residual is preserved, not repaired or assumed to be an opening balance.
    wb, ws = _sheet(SALES_6OCT, "الرئيسية")
    exceptions, checked = [], 0
    try:
        for row_no, (name, _addr, sales, coll, bal) in enumerate(ws.iter_rows(
            min_row=2, max_row=ws.max_row, min_col=1, max_col=5, values_only=True
        ), 2):
            if not isinstance(name, str) or not name.strip() or not _nums(sales, coll, bal):
                continue
            checked += 1
            if abs(bal - (sales - coll)) >= TOL:
                exceptions.append((row_no, name, sales, coll, round(bal, 2)))
        assert exceptions == [(16, "صيدليات الشركة المصرية للأدوية", 0, 0, 16103.56)], exceptions
        assert checked >= 20, checked
        # The unnamed total carries the same known residual; do not call it zero.
        sales, coll, balance = next(ws.iter_rows(min_row=102, max_row=102,
                                                min_col=3, max_col=5, values_only=True))
        assert abs((balance - (sales - coll)) - 16103.56) < TOL
    finally:
        wb.close()


def test_payroll_sheet_structure():
    # المرتبات observed layout: A=الاسم, B=الاساسى(basic), C=المستحق(due),
    # D=واصل(received), E=دوباى(dubai).
    # NOTE: the mapping's payroll formula "E=B-C-D" does NOT match this layout
    # (E is the dubai allowance here) -> flagged in PRE_CODING_VERIFICATION.md,
    # deliberately NOT asserted as a formula.
    wb, ws = _sheet(SALES_DAK, "المرتبات")
    r1 = next(ws.iter_rows(min_row=1, max_row=1, max_col=2, values_only=True))
    r2 = next(ws.iter_rows(min_row=2, max_row=2, max_col=5, values_only=True))
    assert r1[0] == "الاسم"
    assert (r2[1], r2[2], r2[3], r2[4]) == ("الاساسى", "المستحق", "واصل", "دوباى")
    wb.close()
