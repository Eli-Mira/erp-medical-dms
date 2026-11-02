"""Preserve the existing representative target input compatibility contract."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from test_lane1_r22_territory_http import (
    require_owned_verifier_database as require_owned_verifier_database,  # noqa: PLC0414
)


def test_representative_target_ignores_legacy_client_metadata():
    from app.sales.schemas import TargetIn

    representative = uuid4()
    target = TargetIn.model_validate(
        {
            "rep_id": str(representative),
            "period_month": date(2026, 10, 1),
            "target_quantity": "12.500",
            "legacy_client_metadata": "unchanged-old-client",
        }
    )
    assert target.rep_id == representative
    assert target.target_quantity == Decimal("12.500")
    assert "legacy_client_metadata" not in target.model_dump()
