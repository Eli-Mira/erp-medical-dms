"""Invoice calculation — pure functions, no DB.

Business rules (D18 net price, D36 VAT):
- Net price:  E = C × (1 − D)          (per-unit, after discount)
- VAT-inclusive extraction uses rate/(100 + rate), where 14 means 14%.
- Draft policy inherited from Piece 1: Decimal half-up to 2 places. The
  printed-invoice rounding/exemption policy is NOT verified for production.

The unit_price is the VAT-inclusive price the customer pays (matching the
source workbooks, which carry no VAT column). The invoice header breaks the
VAT out: total_net (ex-VAT) + vat_amount = grand_total (incl-VAT).
"""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
ONE = Decimal("1")
HUNDRED = Decimal("100")


def _r2(x: Decimal) -> Decimal:
    """Round a Decimal to 2 places, half-up (money)."""
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def net_price(unit_price: Decimal, discount_pct: Decimal) -> Decimal:
    """E = C × (1 − D). Per-unit net after discount (VAT-inclusive)."""
    return _r2(unit_price * (ONE - discount_pct / HUNDRED))


def vat_amount_for(incl_vat_amount: Decimal, vat_rate: Decimal) -> Decimal:
    """VAT portion of a VAT-inclusive amount.

    `vat_rate` is a percentage (14 = 14%), so r = rate/100 and
    vat = amount × r/(1+r) = amount × rate/(100+rate).
    """
    if vat_rate <= 0:
        return ZERO
    r = vat_rate / HUNDRED
    return _r2(incl_vat_amount * r / (ONE + r))


def line_calc(quantity, unit_price, discount_pct, vat_rate):
    """Compute one invoice line.

    Returns (net_price, line_total, vat_amount):
      net_price  = unit_price × (1 − discount_pct)      [VAT-inclusive per unit]
      line_total = quantity × net_price                [VAT-inclusive]
      vat_amount = line_total × vat_rate/(1+vat_rate)   [VAT portion]
    """
    net = net_price(unit_price, discount_pct)
    total = _r2(quantity * net)
    vat = vat_amount_for(total, vat_rate)
    return net, total, vat


def invoice_totals(lines):
    """Aggregate invoice header totals from line tuples.

    `lines`: iterable of (quantity, unit_price, discount_pct, vat_rate).
    Returns a dict:
      total_before_discount  Σ(qty × unit_price)              [incl-VAT]
      total_discount         total_before_discount − grand_total  [realized, incl-VAT]
      total_net              grand_total − vat_amount         [ex-VAT]
      vat_amount             Σ line vat                        [VAT]
      grand_total            Σ line_total                     [incl-VAT]
    """
    total_before_discount = ZERO
    grand_total = ZERO
    vat_total = ZERO
    for qty, price, disc, rate in lines:
        _net, total, vat = line_calc(qty, price, disc, rate)
        total_before_discount += _r2(qty * price)
        grand_total += total
        vat_total += vat
    total_before_discount = _r2(total_before_discount)
    grand_total = _r2(grand_total)
    vat_total = _r2(vat_total)
    # Discount is derived as the residual (gross − charged) so the reconciliation
    # invariant total_before_discount − total_discount == grand_total holds
    # exactly, avoiding the 1-cent drift from independent per-line rounding of
    # the pct-based discount sum under half-up 2dp net_price rounding.
    total_discount = _r2(total_before_discount - grand_total)
    return {
        "total_before_discount": total_before_discount,
        "total_discount": total_discount,
        "total_net": _r2(grand_total - vat_total),
        "vat_amount": vat_total,
        "grand_total": grand_total,
    }
