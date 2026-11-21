"""Typed physical intake; approval, release and financial settlement stay deferred."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.sales.schemas import Quantity


class ReturnIn(BaseModel):
    # Preserve quarantine intake's existing ignore-forged-lifecycle-fields contract.
    model_config = ConfigDict(extra="ignore")

    customer_id: UUID
    product_id: UUID
    warehouse_id: UUID
    batch_id: UUID | None = None
    quantity: Quantity
    return_date: date
    reason: str | None = None
    invoice_id: UUID | None = None

    @field_validator("reason")
    @classmethod
    def reject_nul(cls, value: str | None) -> str | None:
        if value is not None and "\x00" in value:
            raise ValueError("reason cannot contain NUL")
        return value

from decimal import Decimal
from typing import Literal

class ReturnDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["approved_restock", "scrapped"]
    unit_price: Decimal | None = None
    vat_rate: Decimal | None = None
    issue_credit_note: bool = True
    decision_note: str | None = None

    @field_validator("unit_price")
    @classmethod
    def validate_unit_price(cls, value: Decimal | None) -> Decimal | None:
        if value is not None:
            if not value.is_finite() or value < 0:
                raise ValueError("unit_price must be non-negative and finite")
        return value

    @field_validator("vat_rate")
    @classmethod
    def validate_vat_rate(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value not in (Decimal("0"), Decimal("0.00"), Decimal("14"), Decimal("14.00")):
            raise ValueError("vat_rate must be 0 or 14")
        return value

    @field_validator("decision_note")
    @classmethod
    def reject_note_nul(cls, value: str | None) -> str | None:
        if value is not None and ("\x00" in value or len(value) > 500):
            raise ValueError("invalid decision_note")
        return value
