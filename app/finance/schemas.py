"""AR entry and payment receipt input/output models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Money = Annotated[
    Decimal, Field(ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
]
EntryType = Annotated[str, Field(min_length=1, max_length=20)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*", check_fields=False)
    @classmethod
    def reject_null_characters(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text cannot contain null characters")
        return value


class EntryIn(InputModel):
    customer_id: UUID
    entry_type: Annotated[
        str, Field(pattern="^(opening|payment|credit_note|adjustment)$")
    ]
    debit: Money = Decimal(0)
    credit: Money = Decimal(0)
    entry_date: date
    due_date: date | None = None
    reason_id: UUID | None = None
    note: Annotated[str, Field(max_length=4000)] | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.debit == 0 and self.credit == 0:
            raise ValueError("an entry must debit or credit at least one side")
        if self.entry_type == "adjustment" and self.reason_id is None:
            raise ValueError("adjustment requires a reason code")
        return self


class EntryOut(BaseModel):
    id: UUID
    customer_id: UUID
    invoice_id: UUID | None
    entry_type: str
    entry_date: date
    due_date: date | None
    debit: Decimal
    credit: Decimal
    reason_id: UUID | None
    note: str | None
    created_by: UUID
    created_at: datetime
    receipt_id: UUID | None = None
    reverses_entry_id: UUID | None = None


class ReceiptIn(InputModel):
    # Financial authority (customer/branch/status/actor) is derived server-side.
    invoice_id: UUID
    receipt_no: Annotated[str, Field(min_length=1, max_length=30)]
    receipt_date: date
    amount: Annotated[
        Decimal, Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    ]
    method: Annotated[str, Field(pattern="^(cash|check|transfer)$")]
    note: Annotated[str, Field(max_length=4000)] | None = None
    invoice_version: Annotated[int, Field(ge=1, strict=True)]


class ReceiptVoidIn(InputModel):
    version: Annotated[int, Field(ge=1, strict=True)]
    reason_id: UUID


class ReceiptOut(BaseModel):
    id: UUID
    invoice_id: UUID
    branch_id: UUID
    customer_id: UUID
    receipt_no: str
    receipt_date: date
    amount: Decimal
    method: str
    note: str | None
    status: str
    voided_at: datetime | None
    voided_by: UUID | None
    void_reason_id: UUID | None
    version: int
    created_by: UUID
    created_at: datetime
    updated_by: UUID | None
    updated_at: datetime


class StatementLine(BaseModel):
    id: UUID
    customer_id: UUID
    invoice_id: UUID | None
    entry_type: str
    entry_date: date
    due_date: date | None
    debit: Decimal
    credit: Decimal
    balance: Decimal
    reason_id: UUID | None
    note: str | None
    created_by: UUID
    created_at: datetime
    receipt_id: UUID | None = None
    reverses_entry_id: UUID | None = None


class StatementOut(BaseModel):
    customer_id: UUID
    date_from: date | None
    date_to: date | None
    opening_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
    lines: list[StatementLine]


class AgingCustomer(BaseModel):
    customer_id: UUID
    current: Decimal
    d1_30: Decimal
    d31_60: Decimal
    d61_90: Decimal
    over_90: Decimal
    undated: Decimal
    total: Decimal


class AgingTotals(BaseModel):
    current: Decimal
    d1_30: Decimal
    d31_60: Decimal
    d61_90: Decimal
    over_90: Decimal
    undated: Decimal
    total: Decimal


class AgingOut(BaseModel):
    label: str
    note: str
    as_of: date
    customers: list[AgingCustomer]
    total: AgingTotals
