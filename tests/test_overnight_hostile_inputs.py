"""Schema-bound controls; no business-data writes or guessed frontend selectors."""

from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.finance.schemas import EntryIn, ReceiptIn
from app.marketing.router import ObjectiveInput, SpendInput, _validated
from app.master.schemas import CustomerIn, CustomerPatch, ProductIn, ProductPatch
from app.returns.schemas import ReturnIn
from app.sales.schemas import DraftIn, LineIn
from app.settings.schemas import InventoryPolicyIn

UID = "00000000-0000-4000-8000-000000000001"
DAY = "2026-01-15"
CUSTOMER = {"code": "C1", "name_ar": "عميل", "branch_id": UID, "territory_id": UID}
PRODUCT = {"sku": "P1", "name_ar": "منتج", "base_price": "1.25", "vat_rate": "14.00"}
LINE = {"product_id": UID, "quantity": "1.125", "unit_price": "1.25"}
DRAFT = {
    "invoice_no": "I1",
    "branch_id": UID,
    "warehouse_id": UID,
    "customer_id": UID,
    "invoice_date": DAY,
    "lines": [LINE],
}
ENTRY = {
    "customer_id": UID,
    "entry_type": "opening",
    "debit": "1.25",
    "entry_date": DAY,
}
RECEIPT = {
    "invoice_id": UID,
    "receipt_no": "R1",
    "receipt_date": DAY,
    "amount": "1.25",
    "method": "cash",
    "invoice_version": 1,
}
SPEND = {"spend_date": DAY, "amount": "1.25", "activity_type": "meeting"}
RETURN = {
    "customer_id": UID,
    "product_id": UID,
    "warehouse_id": UID,
    "quantity": "1.125",
    "return_date": DAY,
}
POLICY = {"stock_cover_window_days": 30, "overstock_threshold_days": 180}


@pytest.mark.parametrize(
    "model,payload,field,value",
    [
        (CustomerIn, CUSTOMER, "code", "bad\x00code"),
        (CustomerIn, CUSTOMER, "name_ar", "bad\x00name"),
        (CustomerIn, CUSTOMER, "name_en", "bad\x00name"),
        (CustomerPatch, {"name_ar": "name"}, "name_ar", "bad\x00name"),
        (ProductIn, PRODUCT, "sku", "bad\x00sku"),
        (ProductPatch, {"name_en": "name"}, "name_en", "bad\x00name"),
        (DraftIn, DRAFT, "invoice_no", "bad\x00number"),
        (DraftIn, DRAFT, "notes", "bad\x00note"),
        (LineIn, LINE, "notes", "bad\x00note"),
        (EntryIn, ENTRY, "note", "bad\x00note"),
        (ReceiptIn, RECEIPT, "receipt_no", "bad\x00number"),
        (ReceiptIn, RECEIPT, "note", "bad\x00note"),
        (ReturnIn, RETURN, "reason", "bad\x00reason"),
    ],
    ids=[
        "customer-code",
        "customer-name-ar",
        "customer-name-en",
        "customer-patch",
        "product-sku",
        "product-patch",
        "invoice-number",
        "invoice-notes",
        "line-notes",
        "ar-note",
        "receipt-number",
        "receipt-note",
        "return-reason",
    ],
)
def test_nul_rejected(model, payload, field, value):
    with pytest.raises(ValidationError):
        model.model_validate({**deepcopy(payload), field: value})


@pytest.mark.parametrize(
    "model,payload,field,size",
    [
        (CustomerIn, CUSTOMER, "code", 31),
        (CustomerIn, CUSTOMER, "name_ar", 201),
        (ProductIn, PRODUCT, "sku", 51),
        (ProductIn, PRODUCT, "name_ar", 201),
        (DraftIn, DRAFT, "invoice_no", 31),
        (DraftIn, DRAFT, "notes", 4001),
        (LineIn, LINE, "notes", 2001),
        (EntryIn, ENTRY, "note", 4001),
        (ReceiptIn, RECEIPT, "receipt_no", 31),
        (SpendInput, SPEND, "activity_type", 41),
    ],
)
def test_existing_length_caps(model, payload, field, size):
    with pytest.raises(ValidationError):
        model.model_validate({**deepcopy(payload), field: "x" * size})


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (CustomerIn, CUSTOMER, "is_active"),
        (ProductIn, PRODUCT, "created_by"),
        (DraftIn, DRAFT, "territory_id"),
        (DraftIn, DRAFT, "grand_total"),
        (LineIn, LINE, "vat_rate"),
        (EntryIn, ENTRY, "invoice_id"),
        (ReceiptIn, RECEIPT, "status"),
        (SpendInput, SPEND, "created_by"),
        (ObjectiveInput, {"objective": "follow up"}, "created_by"),
        (InventoryPolicyIn, POLICY, "unexpected"),
    ],
)
def test_unknown_or_server_owned_fields_rejected(model, payload, field):
    with pytest.raises(ValidationError):
        model.model_validate({**deepcopy(payload), field: "forged"})


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (CustomerIn, CUSTOMER, "branch_id"),
        (DraftIn, DRAFT, "customer_id"),
        (EntryIn, ENTRY, "customer_id"),
        (ReceiptIn, RECEIPT, "invoice_id"),
        (SpendInput, SPEND, "territory_id"),
        (ObjectiveInput, {"objective": "follow up"}, "product_id"),
        (ReturnIn, RETURN, "warehouse_id"),
    ],
)
def test_invalid_uuid_rejected(model, payload, field):
    with pytest.raises(ValidationError):
        model.model_validate({**deepcopy(payload), field: "not-a-uuid"})


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (DraftIn, DRAFT, "invoice_date"),
        (EntryIn, ENTRY, "entry_date"),
        (ReceiptIn, RECEIPT, "receipt_date"),
        (SpendInput, SPEND, "spend_date"),
        (ReturnIn, RETURN, "return_date"),
    ],
)
def test_invalid_calendar_date_rejected(model, payload, field):
    with pytest.raises(ValidationError):
        model.model_validate({**deepcopy(payload), field: "2026-02-30"})


@pytest.mark.parametrize(
    "bad", ["NaN", "Infinity", "-Infinity", "-0.01", "1.001", True, False]
)
@pytest.mark.parametrize(
    "model,payload,field",
    [
        (ProductIn, PRODUCT, "base_price"),
        (LineIn, LINE, "unit_price"),
        (EntryIn, ENTRY, "debit"),
        (ReceiptIn, RECEIPT, "amount"),
        (SpendInput, SPEND, "amount"),
    ],
)
def test_invalid_money_rejected(model, payload, field, bad):
    with pytest.raises(ValidationError):
        model.model_validate({**deepcopy(payload), field: bad})


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "0", "1.0001", True, False])
def test_return_quantity_remains_exact_positive_and_finite(bad):
    with pytest.raises(ValidationError):
        ReturnIn.model_validate({**RETURN, "quantity": bad})


@pytest.mark.parametrize(
    "field",
    ["stock_cover_window_days", "overstock_threshold_days", "expiry_warning_days"],
)
@pytest.mark.parametrize("bad", [True, False, "NaN", "Infinity", -1, 0, 1.5])
def test_invalid_day_counts_rejected(field, bad):
    with pytest.raises(ValidationError):
        InventoryPolicyIn.model_validate({**POLICY, field: bad})


@pytest.mark.parametrize("value", [30, "30", 30.0])
def test_existing_non_boolean_day_compatibility_preserved(value):
    policy = InventoryPolicyIn.model_validate(
        {**POLICY, "stock_cover_window_days": value}
    )
    assert policy.stock_cover_window_days == 30


@pytest.mark.parametrize("payload", [[], "not-a-mapping", 1])
def test_non_mapping_settings_payload_is_validation_error(payload):
    with pytest.raises(ValidationError):
        InventoryPolicyIn.model_validate(payload)


@pytest.mark.parametrize(
    "model,payload,field",
    [
        (SpendInput, SPEND, "notes"),
        (ObjectiveInput, {"objective": "follow up"}, "objective"),
        (ObjectiveInput, {"objective": "follow up"}, "expected_kpi"),
    ],
)
def test_marketing_existing_route_validator_rejects_nul_before_database_access(
    model, payload, field
):
    with pytest.raises(HTTPException) as caught:
        _validated({**payload, field: "bad\x00text"}, model, None, {})
    assert caught.value.status_code == 422


def test_return_forged_lifecycle_fields_remain_ignored_not_applied():
    value = ReturnIn.model_validate({**RETURN, "status": "approved", "created_by": UID})
    assert "status" not in value.model_dump()
    assert "created_by" not in value.model_dump()


def test_harmless_text_is_preserved_not_filtered_as_html():
    harmless = "صيدلية <b>A & B</b> O'Neil"
    assert (
        CustomerIn.model_validate({**CUSTOMER, "name_ar": harmless}).name_ar == harmless
    )
    assert (
        ProductIn.model_validate({**PRODUCT, "name_ar": harmless}).name_ar == harmless
    )
    assert DraftIn.model_validate({**DRAFT, "notes": harmless}).notes == harmless
    assert EntryIn.model_validate({**ENTRY, "note": harmless}).note == harmless
    assert SpendInput.model_validate({**SPEND, "notes": harmless}).notes == harmless
    assert ReturnIn.model_validate({**RETURN, "reason": harmless}).reason == harmless
    assert ProductIn.model_validate(PRODUCT).base_price == Decimal("1.25")
