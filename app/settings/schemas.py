from pydantic import BaseModel, Field


class InventoryPolicyOut(BaseModel):
    stock_cover_window_days: int
    overstock_threshold_days: int


class InventoryPolicyIn(BaseModel):
    stock_cover_window_days: int = Field(ge=1, le=365)
    overstock_threshold_days: int = Field(ge=1, le=3650)
