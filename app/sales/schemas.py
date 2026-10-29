"""Validated draft inputs and exact-decimal public invoice snapshots."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[
    Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
]
Percent = Annotated[
    Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False)
]
Quantity = Annotated[
    Decimal, Field(gt=0, max_digits=12, decimal_places=3, allow_inf_nan=False)
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LineIn(InputModel):
    product_id: UUID
    batch_id: UUID | None = None
    quantity: Quantity
    unit_price: Money | None = None
    discount_pct: Percent = Decimal(0)
    notes: Annotated[str, Field(max_length=2000)] | None = None


class DraftIn(InputModel):
    invoice_no: Annotated[str, Field(min_length=1, max_length=30)]
    branch_id: UUID
    warehouse_id: UUID
    customer_id: UUID
    invoice_date: date
    notes: Annotated[str, Field(max_length=4000)] | None = None
    lines: Annotated[list[LineIn], Field(min_length=1, max_length=500)]


class DraftUpdate(DraftIn):
    version: Annotated[int, Field(ge=1, strict=True)]


class VerifiedCostIn(InputModel):
    version: Annotated[int, Field(ge=1, strict=True)]
    unit_cost: Money
    evidence_ref: Annotated[str, Field(min_length=1, max_length=240)]


class VoidIn(InputModel):
    version: Annotated[int, Field(ge=1, strict=True)]
    reason_id: UUID


class LineOut(BaseModel):
    id: UUID
    line_no: int
    product_id: UUID
    batch_id: UUID | None
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    net_price: Decimal
    line_total: Decimal
    vat_rate: Decimal
    vat_amount: Decimal
    notes: str | None


class InvoiceOut(BaseModel):
    id: UUID
    invoice_no: str
    branch_id: UUID
    territory_id: UUID
    warehouse_id: UUID
    customer_id: UUID
    invoice_date: date
    posting_status: Literal["Draft", "Posted", "Voided"]
    total_before_discount: Decimal
    total_discount: Decimal
    total_net: Decimal
    vat_amount: Decimal
    grand_total: Decimal
    notes: str | None
    version: int
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    updated_by: UUID | None
    posted_at: datetime | None
    posted_by: UUID | None
    voided_at: datetime | None
    voided_by: UUID | None
    void_reason_id: UUID | None
    lines: list[LineOut]


class InvoiceListOut(BaseModel):
    """Invoice-header snapshots (no lines); fetch /invoices/{id} for lines."""

    total: int
    items: list[InvoiceOut]


class ReportTotalsOut(BaseModel):
    invoice_count: int
    total_before_discount: Decimal
    total_discount: Decimal
    total_net: Decimal
    vat_amount: Decimal
    grand_total: Decimal


class ReportTerritoryRow(BaseModel):
    territory_id: UUID
    code: str
    name_ar: str
    invoice_count: int
    total_net: Decimal
    vat_amount: Decimal
    grand_total: Decimal


class ReportRepRow(BaseModel):
    user_id: UUID
    username: str
    invoice_count: int
    total_net: Decimal
    vat_amount: Decimal
    grand_total: Decimal


class ReportProductRow(BaseModel):
    product_id: UUID
    sku: str
    name_ar: str
    quantity: Decimal
    line_total: Decimal
    vat_amount: Decimal


class InvoiceReportOut(BaseModel):
    """Posted-only sales performance aggregates; drafts never appear (PRD)."""

    totals: ReportTotalsOut
    by_territory: list[ReportTerritoryRow]
    by_rep: list[ReportRepRow]
    by_product: list[ReportProductRow]


class TargetIn(BaseModel):
    """Set-or-replace one monthly target; product omitted = rep's whole book."""

    rep_id: UUID
    product_id: UUID | None = None
    period_month: date
    target_quantity: Decimal = Field(ge=0, decimal_places=3, max_digits=12)


class TargetOut(BaseModel):
    """One target row with the actual posted sales for the same scope."""

    id: UUID
    rep_id: UUID
    product_id: UUID | None
    period_month: date
    target_quantity: Decimal
    actual_quantity: Decimal | None
    created_by: UUID
    created_at: datetime
