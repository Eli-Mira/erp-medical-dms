"""Supervisor-owned acceptance oracle; worker must not edit this file."""
import os

import pytest
from pydantic import ValidationError
from sqlalchemy import text

from app.db import engine
from app.settings.schemas import InventoryPolicyIn

pytest_plugins = ["test_inventory_api"]
FIELDS = ("stock_cover_window_days", "overstock_threshold_days")


@pytest.fixture(autouse=True)
def disposable_only():
    assert os.environ.get("APP_ENV") == "test"
    assert engine.url.database.startswith("dms_cycle_test_")


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [True, False], ids=["true", "false"])
def test_policy_boolean_is_not_a_day_count(field, value):
    payload = dict(stock_cover_window_days=30, overstock_threshold_days=180)
    payload[field] = value
    with pytest.raises(ValidationError):
        InventoryPolicyIn.model_validate(payload)


@pytest.mark.parametrize("values,expected", [
    ((30, 180), (30, 180)),
    ((1, 1), (1, 1)),
    ((365, 3650), (365, 3650)),
    (("30", "180"), (30, 180)),
    ((30.0, 180.0), (30, 180)),
])
def test_existing_non_boolean_compatibility(values, expected):
    result = InventoryPolicyIn.model_validate(dict(zip(FIELDS, values)))
    assert (result.stock_cover_window_days, result.overstock_threshold_days) == expected


@pytest.mark.parametrize("field,value", [
    ("stock_cover_window_days", 0),
    ("stock_cover_window_days", 366),
    ("overstock_threshold_days", 0),
    ("overstock_threshold_days", 3651),
])
def test_existing_bounds_remain(field, value):
    payload = dict(stock_cover_window_days=30, overstock_threshold_days=180)
    payload[field] = value
    with pytest.raises(ValidationError):
        InventoryPolicyIn.model_validate(payload)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("value", [True, False], ids=["true", "false"])
def test_boolean_request_is_422_without_setting_or_audit_writes(stock_env, field, value):
    client, db, _ids, headers, _movement = stock_env
    auth = headers("owner")
    settings_before = db.execute(text(
        "SELECT key, value FROM platform.platform_setting ORDER BY key"
    )).all()
    audit_before = db.execute(text("SELECT count(*) FROM audit.audit_log")).scalar_one()
    payload = dict(stock_cover_window_days=30, overstock_threshold_days=180)
    payload[field] = value
    result = client.put("/settings/inventory-policy", json=payload, headers=auth)
    assert result.status_code == 422, result.text
    assert db.execute(text(
        "SELECT key, value FROM platform.platform_setting ORDER BY key"
    )).all() == settings_before
    assert db.execute(text("SELECT count(*) FROM audit.audit_log")).scalar_one() == audit_before
