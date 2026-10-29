"""Approved read-only query templates for Telegram analyst.

NEVER let an LLM write or run free-form SQL. Only these templates are allowed.
Each template takes named parameters and returns a short answer string.
"""
from sqlalchemy import text
from decimal import Decimal
from typing import Callable, Dict, Any, List, Optional


# Query template definitions: name -> (sql, params, formatter)
# All queries run against a read-only DB role with user's role scope.

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "balance": {
        "description": "Customer balance summary",
        "sql": """
            SELECT c.name, COALESCE(SUM(i.total - i.paid), 0) AS balance
            FROM customers c
            LEFT JOIN invoices i ON i.customer_id = c.id AND i.status != 'void'
            WHERE c.id = :customer_id
            GROUP BY c.id, c.name
        """,
        "params": ["customer_id"],
        "format": lambda rows: (
            f"Customer: {rows[0][0]}\nBalance: {Decimal(str(rows[0][1])):.2f} EGP"
            if rows else "Customer not found"
        ),
    },
    "stock": {
        "description": "Current stock for a product",
        "sql": """
            SELECT p.name, COALESCE(SUM(s.qty_on_hand), 0) AS qty
            FROM products p
            LEFT JOIN stock_lines s ON s.product_id = p.id
            WHERE p.id = :product_id
            GROUP BY p.id, p.name
        """,
        "params": ["product_id"],
        "format": lambda rows: (
            f"Product: {rows[0][0]}\nStock: {rows[0][1]} units"
            if rows else "Product not found"
        ),
    },
    "sales_today": {
        "description": "Today's sales total",
        "sql": """
            SELECT COALESCE(SUM(total), 0) AS total, COUNT(*) AS count
            FROM invoices
            WHERE DATE(created_at) = CURRENT_DATE AND status != 'void'
        """,
        "params": [],
        "format": lambda rows: (
            f"Today's sales: {Decimal(str(rows[0][0])):.2f} EGP\n"
            f"Invoices: {rows[0][1]}"
        ),
    },
    "expiry": {
        "description": "Products expiring within N days",
        "sql": """
            SELECT p.name, b.batch_number, b.expiry_date, b.qty_on_hand
            FROM batches b
            JOIN products p ON p.id = b.product_id
            WHERE b.expiry_date <= CURRENT_DATE + :days
              AND b.qty_on_hand > 0
            ORDER BY b.expiry_date ASC
            LIMIT 20
        """,
        "params": ["days"],
        "format": lambda rows: (
            "\n".join(
                f"{r[0]} (batch {r[1]}): {r[3]} units, expires {r[2]}"
                for r in rows
            ) if rows else "No products expiring within the period"
        ),
    },
    "targets": {
        "description": "Sales target progress for a period",
        "sql": """
            SELECT t.target_amount, COALESCE(SUM(i.total), 0) AS achieved
            FROM sales_targets t
            LEFT JOIN invoices i ON i.created_at >= t.start_date
                AND i.created_at <= t.end_date AND i.status != 'void'
            WHERE t.id = :target_id
            GROUP BY t.id, t.target_amount
        """,
        "params": ["target_id"],
        "format": lambda rows: (
            f"Target: {Decimal(str(rows[0][0])):.2f} EGP\n"
            f"Achieved: {Decimal(str(rows[0][1])):.2f} EGP\n"
            f"Progress: {float(rows[0][1]) / float(rows[0][0]) * 100:.1f}%"
            if rows and float(rows[0][0]) > 0
            else "Target not found"
        ),
    },
    "stock_cover": {
        "description": "Stock cover (days of supply) for a product",
        "sql": """
            SELECT p.name,
                   COALESCE(SUM(s.qty_on_hand), 0) AS qty,
                   COALESCE(AVG(daily.qty_sold), 0) AS avg_daily
            FROM products p
            LEFT JOIN stock_lines s ON s.product_id = p.id
            LEFT JOIN (
                SELECT product_id, SUM(qty) / 30.0 AS qty_sold
                FROM invoice_lines il
                JOIN invoices i ON i.id = il.invoice_id
                WHERE i.created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY product_id
            ) daily ON daily.product_id = p.id
            WHERE p.id = :product_id
            GROUP BY p.id, p.name
        """,
        "params": ["product_id"],
        "format": lambda rows: (
            f"Product: {rows[0][0]}\n"
            f"Stock: {rows[0][1]} units\n"
            f"Avg daily sales: {float(rows[0][2]):.1f}\n"
            f"Cover: {float(rows[0][1]) / max(float(rows[0][2]), 0.01):.1f} days"
            if rows else "Product not found"
        ),
    },
}

# Keyword → template mapping (analyst layer)
KEYWORD_MAP = {
    "balance": ["balance", "رصيد", "مديونية", "debt", "owed"],
    "stock": ["stock", "مخزون", "كمية", "quantity", "how many"],
    "sales_today": ["sales today", "مبيعات اليوم", "today sales", "today's sales"],
    "expiry": ["expiry", "expiry", "انتهاء", "صلاحية", "expiring", "expire"],
    "targets": ["target", "هدف", "goals", "هدف المبيعات"],
    "stock_cover": ["stock cover", "cover", "تغطية", "days of supply", "أيام التغطية"],
}


def match_template(question: str) -> Optional[str]:
    """Map a natural language question to an approved template name."""
    q = question.lower()
    # Check longer keywords first to avoid false matches (e.g., "stock cover" before "stock")
    best_match = None
    best_len = 0
    for template_name, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in q and len(kw) > best_len:
                best_match = template_name
                best_len = len(kw)
    return best_match


def get_template(name: str) -> Optional[Dict[str, Any]]:
    return TEMPLATES.get(name)


def list_templates() -> List[str]:
    return list(TEMPLATES.keys())
