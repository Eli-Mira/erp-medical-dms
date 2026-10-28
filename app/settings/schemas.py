from typing import Any

from pydantic import BaseModel, Field, model_validator


class InventoryPolicyOut(BaseModel):
    stock_cover_window_days: int
    overstock_threshold_days: int
    expiry_warning_days: int


class InventoryPolicyIn(BaseModel):
    stock_cover_window_days: int = Field(ge=1, le=365)
    overstock_threshold_days: int = Field(ge=1, le=3650)
    expiry_warning_days: int = Field(ge=1, le=365, default=30)

    @staticmethod
    def _normalize_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if payload is None:
            return None
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, bool):
                raise ValueError(
                    "inventory-policy day counts must be plain numbers, not booleans"
                )
            if isinstance(value, str):
                try:
                    value = int(value)
                except ValueError as exc:
                    raise ValueError(
                        f"{key} must be an integer or numeric string, got {value!r}"
                    ) from exc
            if isinstance(value, float) and not value.is_integer():
                raise ValueError(
                    f"{key} must be an integer when given a float, got {value!r}"
                )
            if isinstance(value, float):
                value = int(value)
            cleaned[key] = value
        return cleaned

    @model_validator(mode="before")
    @classmethod
    def _coerce_day_counts(cls, data):
        data = cls._normalize_payload(data)
        if not isinstance(data, dict):
            return data
        for key in ("stock_cover_window_days", "overstock_threshold_days", "expiry_warning_days"):
            value = data.get(key)
            if isinstance(value, bool):
                raise ValueError(
                    "inventory-policy day counts must be plain numbers, not booleans"
                )
            if isinstance(value, str):
                data[key] = int(value)
            elif isinstance(value, float):
                if not value.is_integer():
                    raise ValueError(
                        f"{key} must be an integer when given a float, got {value!r}"
                    )
                data[key] = int(value)
        return data
