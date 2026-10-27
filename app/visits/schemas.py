"""Customer stock-visit schemas (V2 §2B.10, §2B.11).

One visit carries one or more lines. Sell-through is not a client field the
caller can fudge: the API computes it from the four quantity inputs and the
schema rejects anything that disagrees, so the CHECK on the table is the
enforcement, not a promise in the UI.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Quantity = Annotated[
    Decimal, Field(ge=0, max_digits=12, decimal_places=3, allow_inf_nan=False)
]
Money = Annotated[
    Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
]


class VisitLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: UUID
    batch_id: UUID | None = None
    quantity_prev: Quantity = Decimal(0)
    quantity_delivered: Quantity = Decimal(0)
    quantity_returned: Quantity = Decimal(0)
    quantity_current: Quantity = Decimal(0)
    amount: Money = Decimal(0)
    payment_method: Annotated[str, Field(max_length=30)] | None = None
    notes: Annotated[str, Field(max_length=2000)] | None = None

    @model_validator(mode="after")
    def validate_sell_through(self):
        sold = (
            self.quantity_prev
            + self.quantity_delivered
            - self.quantity_returned
            - self.quantity_current
        )
        if not Decimal(0) <= sold <= Decimal("999999999.999"):
            raise ValueError(
                "sell-through must be nonnegative and fit quantity precision"
            )
        return self


class VisitIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    customer_id: UUID
    visit_date: date
    notes: Annotated[str, Field(max_length=4000)] | None = None
    lines: Annotated[list[VisitLineIn], Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def unique_products(self):
        if len({line.product_id for line in self.lines}) != len(self.lines):
            raise ValueError("each product may appear only once per visit")
        return self


class VisitLineOut(BaseModel):
    id: UUID
    visit_id: UUID
    product_id: UUID
    batch_id: UUID | None
    quantity_prev: Decimal
    quantity_delivered: Decimal
    quantity_returned: Decimal
    quantity_current: Decimal
    sell_through: Decimal
    amount: Decimal
    payment_method: str | None
    notes: str | None


class VisitOut(BaseModel):
    id: UUID
    customer_id: UUID
    rep_id: UUID
    visit_date: date
    notes: str | None
    created_by: UUID
    created_at: datetime
    lines: list[VisitLineOut]


class VisitListOut(BaseModel):
    total: int
    items: list[VisitOut]


class HeldStockLineOut(BaseModel):
    id: UUID
    customer_id: UUID
    product_id: UUID
    batch_id: UUID | None
    quantity_on_hand: Decimal
    last_visit_id: UUID | None
    updated_at: datetime


class HeldStockListOut(BaseModel):
    total: int
    items: list[HeldStockLineOut]
