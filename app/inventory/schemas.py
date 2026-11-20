"""Validated stock-movement input and exact-decimal ledger/balance snapshots."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]
# Signed: positive is stock in, negative is stock out.
SignedQuantity = Annotated[Decimal, Field(max_digits=12, decimal_places=3, allow_inf_nan=False)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", check_fields=False)
    @classmethod
    def reject_null_characters(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text cannot contain null characters")
        return value


class MovementIn(InputModel):
    warehouse_id: UUID
    product_id: UUID
    batch_id: UUID | None = None
    # 'sale', 'return' and 'transfer_*' are reserved for posting/transfers and
    # stay unaccepted here while invoice posting is disabled.
    movement_type: Literal["opening", "adjustment"]
    quantity: SignedQuantity
    unit_cost: Money | None = None
    reason_id: UUID | None = None
    note: Annotated[str, Field(max_length=2000)] | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.quantity == 0:
            raise ValueError("quantity must not be zero")
        if self.movement_type == "opening" and self.quantity < 0:
            raise ValueError("opening quantity must be positive")
        if self.movement_type == "adjustment" and self.reason_id is None:
            raise ValueError("adjustment requires a reason code")
        return self


class BalanceOut(BaseModel):
    warehouse_id: UUID
    product_id: UUID
    batch_id: UUID | None
    quantity: Decimal
    updated_at: datetime
    warehouse_name: str | None = None
    product_name: str | None = None


class CoverOut(BaseModel):
    warehouse_id: UUID
    product_id: UUID
    on_hand: Decimal
    sold_in_window: Decimal | None
    avg_daily_sales: Decimal | None
    cover_days: Decimal | None
    window_days: int
    threshold_days: int
    status: str


class BatchOut(BaseModel):
    id: UUID
    product_id: UUID
    warehouse_id: UUID
    batch_no: str
    manufacture_date: date | None
    expiry_date: date
    quantity: Decimal


class MovementOut(BaseModel):
    id: UUID
    warehouse_id: UUID
    product_id: UUID
    batch_id: UUID | None
    movement_type: str
    quantity: Decimal
    unit_cost: Decimal | None
    cost_status: Literal["cost_unverified", "cost_verified"]
    source_type: str | None
    source_id: UUID | None
    note: str | None
    created_by: UUID
    created_at: datetime


class MovementResult(BaseModel):
    movement: MovementOut
    balance_quantity: Decimal


class ExpiryWarningOut(BaseModel):
    """Batch near-expiry warning with remaining days and current balance."""
    id: UUID
    product_id: UUID
    warehouse_id: UUID
    batch_no: str
    manufacture_date: date | None
    expiry_date: date
    days_until_expiry: int
    quantity: Decimal
