"""Customer stock-visit schemas (V2 §2B.10, §2B.11).

One visit carries one or more lines. Sell-through is not a client field the
caller can fudge: the API computes it from the four quantity inputs and the
schema rejects anything that disagrees, so the CHECK on the table is the
enforcement, not a promise in the UI.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Quantity = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=3, allow_inf_nan=False)]
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]


class VisitLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: UUID
    batch_id: Optional[UUID] = None
    quantity_prev: Quantity = Decimal(0)
    quantity_delivered: Quantity = Decimal(0)
    quantity_returned: Quantity = Decimal(0)
    quantity_current: Quantity = Decimal(0)
    amount: Money = Decimal(0)
    payment_method: Annotated[str, Field(max_length=30)] | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None


class VisitIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_id: UUID
    visit_date: date
    notes: Annotated[str, Field(max_length=4000)] | None = None
    lines: Annotated[list[VisitLineIn], Field(min_length=1, max_length=500)]


class VisitLineOut(BaseModel):
    id: UUID
    visit_id: UUID
    product_id: UUID
    batch_id: Optional[UUID]
    quantity_prev: Decimal
    quantity_delivered: Decimal
    quantity_returned: Decimal
    quantity_current: Decimal
    sell_through: Decimal
    amount: Decimal
    payment_method: Optional[str]
    notes: Optional[str]


class VisitOut(BaseModel):
    id: UUID
    customer_id: UUID
    rep_id: UUID
    visit_date: date
    notes: Optional[str]
    created_by: UUID
    created_at: datetime
    lines: list[VisitLineOut]


class VisitListOut(BaseModel):
    total: int
    items: list[VisitOut]