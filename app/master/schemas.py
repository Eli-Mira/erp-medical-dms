"""Read-only master-data snapshots used to populate the invoice UI.

These are deliberately thin: only the fields the invoice screen needs to build
a draft, with the same decimal types the invoice API validates against.
"""
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


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
