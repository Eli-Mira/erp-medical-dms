"""Unit tests for invoice calculation (VAT-inclusive, D36; net price, D18).

These are pure-function tests — no DB. They lock the financial rules:
net price E = C × (1 − D), VAT extracted as amount × rate/(1+rate), and
half-up 2-decimal rounding.
"""
from decimal import Decimal

from app.sales.calc import (
    invoice_totals,
    line_calc,
    net_price,
    vat_amount_for,
)


def test_net_price_matches_excel_formula():
    # Excel transaction sheets: E = C × (1 − D)
    assert net_price(Decimal("250"), Decimal("30")) == Decimal("175.00")
    assert net_price(Decimal("180"), Decimal("30")) == Decimal("126.00")
    assert net_price(Decimal("95"), Decimal("30")) == Decimal("66.50")
    assert net_price(Decimal("100"), Decimal("0")) == Decimal("100.00")


def test_vat_extracted_from_inclusive_amount():
    # 14% VAT-inclusive: vat = amount × 14/114
    assert vat_amount_for(Decimal("114"), Decimal("14")) == Decimal("14.00")
    assert vat_amount_for(Decimal("100"), Decimal("14")) == Decimal("12.28")
    assert vat_amount_for(Decimal("0"), Decimal("14")) == Decimal("0.00")
    # rate 0 (exempt product) -> no VAT
    assert vat_amount_for(Decimal("1000"), Decimal("0")) == Decimal("0.00")


def test_line_calc():
    net, total, vat = line_calc(Decimal("10"), Decimal("100"), Decimal("30"), Decimal("14"))
    assert net == Decimal("70.00")
    assert total == Decimal("700.00")
    assert vat == Decimal("85.96")  # 700 × 14/114


def test_invoice_totals_sum_lines_consistently():
    lines = [
        (Decimal("10"), Decimal("100"), Decimal("30"), Decimal("14")),
        (Decimal("2"), Decimal("250"), Decimal("25"), Decimal("14")),
    ]
    t = invoice_totals(lines)
    # line1: net 70.00, total 700.00, vat 85.96
    # line2: net 187.50, total 375.00, vat 46.05
    assert t["total_before_discount"] == Decimal("1500.00")  # 10×100 + 2×250
    assert t["total_discount"] == Decimal("425.00")          # 300 + 125
    assert t["grand_total"] == Decimal("1075.00")            # 700 + 375
    assert t["vat_amount"] == Decimal("132.01")               # 85.96 + 46.05
    assert t["total_net"] == Decimal("942.99")                # 1075 − 132.01
    # internal consistency
    assert t["total_before_discount"] - t["total_discount"] == t["grand_total"]
    assert t["total_net"] + t["vat_amount"] == t["grand_total"]


def test_line_total_is_vat_inclusive():
    # ex-VAT net + vat == VAT-inclusive line total
    _net, total, vat = line_calc(Decimal("1"), Decimal("114"), Decimal("0"), Decimal("14"))
    assert total == Decimal("114.00")
    assert vat == Decimal("14.00")
    assert total - vat == Decimal("100.00")  # ex-VAT


def test_rounding_half_up():
    # 100 × 14/114 = 12.2807... -> 12.28
    assert vat_amount_for(Decimal("100"), Decimal("14")) == Decimal("12.28")
    # 333.33 × 0.5% discount path: net = 333.33 × (1 − 0.005)
    assert net_price(Decimal("333.33"), Decimal("0.5")) == Decimal("331.66")
