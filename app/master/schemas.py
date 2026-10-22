"""Read-only master-data snapshots used to populate the invoice UI.

These are deliberately thin: only the fields the invoice screen needs to build
a draft, with the same decimal types the invoice API validates against.
"""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class BranchOut(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str | None


class WarehouseOut(BaseModel):
    id: UUID
    branch_id: UUID
    code: str
    name_ar: str
    name_en: str | None
    is_active: bool


class CustomerOut(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str | None
    branch_id: UUID | None
    territory_id: UUID | None


class ProductOut(BaseModel):
    id: UUID
    sku: str
    name_ar: str
    name_en: str | None
    base_price: Decimal
    vat_rate: Decimal


class SupplierOut(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str | None
    contact_phone: str | None
    address: str | None
    is_active: bool


class AccountOut(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str | None
    account_type: str
    parent_id: UUID | None
    is_active: bool


class DoctorOut(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str | None
    specialty: str | None
    branch_id: UUID | None
    contact_phone: str | None
    is_active: bool


class SupplierIn(BaseModel):
    """POST /master/suppliers input.

    Owner-only write boundary: unknown fields are forbidden, required values
    are trimmed/nonblank with length caps, and is_active defaults to true on
    the server (never accepted from the client).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=30)
    name_ar: str = Field(min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None)


class SupplierPatch(BaseModel):
    """PATCH /master/suppliers input: explicit partial fields.

    Only the submitted columns change; server-controlled fields (id,
    created_at, audit actor) are forbidden. Null is rejected for code,
    name_ar and is_active; free-text fields may clear to null.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str | None = Field(default=None, min_length=1, max_length=30)
    name_ar: str | None = Field(default=None, min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None)
    is_active: StrictBool | None = None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one supplier field is required")
        for field in ("code", "name_ar", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
