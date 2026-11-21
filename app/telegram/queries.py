from decimal import Decimal
from typing import Any, Dict, List, Optional

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "balance": {
        "description": "Get customer balance",
        "sql": (
            "SELECT COALESCE(c.name_ar, c.name_en, c.code) AS name, "
            "COALESCE(SUM(e.debit - e.credit), 0) AS balance "
            "FROM master_data.master_customer c "
            "LEFT JOIN finance.ar_entry e ON e.customer_id = c.id "
            "WHERE c.id = :customer_id "
            "GROUP BY c.id, c.name_ar, c.name_en, c.code"
        ),
        "params": ["customer_id"],
        "format": lambda rows: (
            f"Customer: {rows[0][0]}\n"
            f"Balance: {Decimal(str(rows[0][1])):.2f} EGP"
            if rows else "Customer not found"
        ),
    },
    "stock": {
        "description": "Get product stock level",
        "sql": (
            "SELECT COALESCE(p.name_ar, p.name_en, p.sku) AS name, "
            "COALESCE(SUM(s.quantity), 0) AS qty "
            "FROM master_data.master_product p "
            "LEFT JOIN inventory.stock_balance s ON s.product_id = p.id "
            "WHERE p.id = :product_id "
            "GROUP BY p.id, p.name_ar, p.name_en, p.sku"
        ),
        "params": ["product_id"],
        "format": lambda rows: (
            f"Product: {rows[0][0]}\n"
            f"Stock: {Decimal(str(rows[0][1])):.3f} units"
            if rows else "Product not found"
        ),
    },
    "sales_today": {
        "description": "Today's sales summary",
        "sql": (
            "SELECT COALESCE(SUM(grand_total), 0) AS total, COUNT(*) AS count "
            "FROM sales.sales_invoice "
            "WHERE invoice_date = CURRENT_DATE AND posting_status = 'Posted'"
        ),
        "params": [],
        "format": lambda rows: (
            f"Today's sales: {Decimal(str(rows[0][0])):.2f} EGP\n"
            f"Invoices: {rows[0][1]}"
        ),
    },
    "expiry": {
        "description": "Products expiring soon",
        "sql": (
            "SELECT COALESCE(p.name_ar, p.name_en, p.sku) AS name, b.batch_no, "
            "b.expiry_date, s.quantity "
            "FROM inventory.batch_record b "
            "JOIN master_data.master_product p ON p.id = b.product_id "
            "JOIN inventory.stock_balance s ON s.batch_id = b.id "
            "AND s.product_id = b.product_id AND s.warehouse_id = b.warehouse_id "
            "WHERE b.expiry_date <= CURRENT_DATE + (:days * INTERVAL '1 day') "
            "AND s.quantity > 0 "
            "ORDER BY b.expiry_date ASC, b.batch_no ASC "
            "LIMIT 20"
        ),
        "params": ["days"],
        "format": lambda rows: (
            "\n".join(
                f"{r[0]} (batch {r[1]}): {Decimal(str(r[3])):.3f} units, expires {r[2]}"
                for r in rows
            )
            if rows
            else "No products expiring within the period"
        ),
    },
    "targets": {
        "description": "Sales target progress",
        "sql": (
            "SELECT t.target_quantity, COALESCE(SUM(l.quantity), 0) AS achieved "
            "FROM sales.sales_target t "
            "LEFT JOIN sales.sales_invoice i ON i.posting_status = 'Posted' "
            "AND date_trunc('month', i.invoice_date)::date = t.period_month "
            "AND ((t.rep_id IS NOT NULL AND i.rep_id = t.rep_id) "
            "OR (t.territory_id IS NOT NULL AND i.territory_id = t.territory_id)) "
            "LEFT JOIN sales.sales_invoice_line l ON l.invoice_id = i.id "
            "AND (t.product_id IS NULL OR l.product_id = t.product_id) "
            "WHERE t.id = :target_id "
            "GROUP BY t.id, t.target_quantity"
        ),
        "params": ["target_id"],
        "format": lambda rows: (
            f"Target: {Decimal(str(rows[0][0])):.3f} units\n"
            f"Achieved: {Decimal(str(rows[0][1])):.3f} units\n"
            f"Progress: {(Decimal(str(rows[0][1])) / Decimal(str(rows[0][0])) * Decimal('100')):.1f}%"
            if rows and Decimal(str(rows[0][0])) > 0
            else "Target not found"
        ),
    },
    "stock_cover": {
        "description": "Stock cover calculation",
        "sql": (
            "SELECT COALESCE(p.name_ar, p.name_en, p.sku) AS name, "
            "COALESCE(SUM(s.quantity), 0) AS qty, "
            "COALESCE(MAX(daily.qty_sold), 0) AS avg_daily "
            "FROM master_data.master_product p "
            "LEFT JOIN inventory.stock_balance s ON s.product_id = p.id "
            "LEFT JOIN ("
            "SELECT l.product_id, SUM(l.quantity) / 30.0 AS qty_sold "
            "FROM sales.sales_invoice_line l "
            "JOIN sales.sales_invoice i ON i.id = l.invoice_id "
            "WHERE i.posting_status = 'Posted' "
            "AND i.invoice_date >= CURRENT_DATE - INTERVAL '30 days' "
            "GROUP BY l.product_id"
            ") daily ON daily.product_id = p.id "
            "WHERE p.id = :product_id "
            "GROUP BY p.id, p.name_ar, p.name_en, p.sku"
        ),
        "params": ["product_id"],
        "format": lambda rows: (
            f"Product: {rows[0][0]}\n"
            f"Stock: {Decimal(str(rows[0][1])):.3f} units\n"
            f"Avg daily sales: {float(rows[0][2]):.1f}\n"
            f"Cover: {float(rows[0][1]) / max(float(rows[0][2]), 0.01):.1f} days"
            if rows
            else "Product not found"
        ),
    },
}

KEYWORD_MAP = {
    "balance": ["balance", "رصيد", "مديونية", "debt", "owed"],
    "stock": ["stock", "مخزون", "كمية", "quantity", "how many"],
    "sales_today": ["sales today", "مبيعات اليوم", "today sales", "today's sales"],
    "expiry": ["expiry", "انتهاء", "صلاحية", "expiring", "expire"],
    "targets": ["target", "هدف", "goals", "هدف المبيعات"],
    "stock_cover": ["stock cover", "cover", "تغطية", "days of supply", "أيام التغطية"],
}


def match_template(question: str) -> Optional[str]:
    q = question.lower()
    best_match: Optional[str] = None
    best_len = -1
    for tmpl_name, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw.lower() in q:
                if len(tmpl_name) > best_len:
                    best_match = tmpl_name
                    best_len = len(tmpl_name)
                break
    return best_match


def get_template(name: str) -> Optional[Dict[str, Any]]:
    return TEMPLATES.get(name)


def list_templates() -> List[str]:
    return list(TEMPLATES.keys())
