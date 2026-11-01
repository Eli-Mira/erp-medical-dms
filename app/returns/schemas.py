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
