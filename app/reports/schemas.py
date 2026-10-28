"""Public shapes for the management summary; money stays exact Decimal."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class SalesSummary(BaseModel):
    invoices_today: int
    grand_total_today: Decimal
    net_today: Decimal
    vat_today: Decimal
    invoices_mtd: int
    grand_total_mtd: Decimal
    net_mtd: Decimal
    vat_mtd: Decimal


class CollectionsSummary(BaseModel):
    receipts_today: int
    amount_today: Decimal
    receipts_mtd: int
    amount_mtd: Decimal


class ReceivablesSummary(BaseModel):
    outstanding_total: Decimal
    customers_with_balance: int


class InventoryAlertsSummary(BaseModel):
    overstock_count: int
    no_sales_history_count: int
    window_days: int
    threshold_days: int


class ManagementSummaryOut(BaseModel):
    as_of: date
    sales: SalesSummary
    collections: CollectionsSummary
    receivables: ReceivablesSummary
    inventory_alerts: InventoryAlertsSummary
