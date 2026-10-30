"""Read-only master-data snapshots used to populate the invoice UI.

These are deliberately thin: only the fields the invoice screen needs to build
a draft, with the same decimal types the invoice API validates against.
"""

from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


class BranchOut(BaseModel):
    id: UUID
    code: str
    name_ar: str
    name_en: str | None


class TerritoryOut(BaseModel):
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
    is_active: bool
    contact_phone: str | None = None
    address: str | None = None


class CustomerPatch(BaseModel):
    """Partial owner edits; identity, branch, territory and status stay server-owned."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name_ar: str | None = Field(default=None, min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = None

    @field_validator("contact_phone", "address")
    @classmethod
    def normalize_contact(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("Contact fields cannot contain null characters")
        return value or None

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one customer field is required")
        if "name_ar" in self.model_fields_set and self.name_ar is None:
            raise ValueError("name_ar cannot be null")
        return self


class CustomerIn(BaseModel):
    """POST /master/customers input.

    Owner-only write boundary: unknown fields are forbidden, required values
    are trimmed/nonblank with length caps, and is_active defaults to true on
    the server (never accepted from the client).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=30)
    name_ar: str = Field(min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    branch_id: UUID
    territory_id: UUID
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = None

    @field_validator("contact_phone", "address")
    @classmethod
    def normalize_contact(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("Contact fields cannot contain null characters")
        return value or None


class ProductOut(BaseModel):
    id: UUID
    sku: str
    name_ar: str
    name_en: str | None
    base_price: Decimal
    vat_rate: Decimal


class ProductIn(BaseModel):
    """Explicit owner-entered catalog values; no inferred financial defaults."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sku: str = Field(min_length=1, max_length=50)
    name_ar: str = Field(min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    base_price: Decimal = Field(
        ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False
    )
    vat_rate: Decimal = Field(
        ge=0, le=100, max_digits=5, decimal_places=2, allow_inf_nan=False
    )

    @field_validator("base_price", "vat_rate", mode="before")
    @classmethod
    def reject_inexact_inputs(cls, value):
        if isinstance(value, (bool, float)):
            # Pydantic converts ValueError to HTTP422; TypeError would escape validation.
            raise ValueError("Use a decimal string or integer, not a float or boolean")  # noqa: TRY004
        return value

    @field_validator("sku", "name_ar", "name_en")
    @classmethod
    def reject_null_characters(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("Product fields cannot contain null characters")
        return value


class ProductPatch(BaseModel):
    """Identity edits only; SKU, prices, VAT and activity use no ordinary patch."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name_ar: str | None = Field(default=None, min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)

    @field_validator("name_ar", "name_en")
    @classmethod
    def reject_null_characters(cls, value):
        if value is not None and "\x00" in value:
            raise ValueError("Product fields cannot contain null characters")
        return value

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one product field is required")
        if "name_ar" in self.model_fields_set and self.name_ar is None:
            raise ValueError("name_ar cannot be null")
        return self


class ProductMaintenanceOut(ProductOut):
    is_active: bool


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
