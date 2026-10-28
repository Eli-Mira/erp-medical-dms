"""Read/write the three approved inventory-policy settings (D41, expiry warnings)."""

from uuid import UUID

from sqlalchemy import text

# D41-approved defaults; DB rows are the override, never hardcode in logic.
WINDOW_KEY = "stock_cover_window_days"
THRESHOLD_KEY = "overstock_threshold_days"
EXPIRY_KEY = "expiry_warning_days"
DEFAULT_WINDOW_DAYS = 30
DEFAULT_THRESHOLD_DAYS = 180
DEFAULT_EXPIRY_DAYS = 30


def _as_int(value, fallback):
    """DB rows are our validated writes; fall back for manual DB edits."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def read_policy(db):
    rows = db.execute(
        text("SELECT key, value FROM platform.platform_setting WHERE key IN (:w, :t, :e)"),
        {"w": WINDOW_KEY, "t": THRESHOLD_KEY, "e": EXPIRY_KEY},
    ).mappings().all()
    values = {row["key"]: row["value"] for row in rows}
    return {
        "stock_cover_window_days": _as_int(values.get(WINDOW_KEY), DEFAULT_WINDOW_DAYS),
        "overstock_threshold_days": _as_int(values.get(THRESHOLD_KEY), DEFAULT_THRESHOLD_DAYS),
        "expiry_warning_days": _as_int(values.get(EXPIRY_KEY), DEFAULT_EXPIRY_DAYS),
    }


def write_policy(db, actor_id: UUID, window: int, threshold: int, expiry: int):
    db.execute(
        text("""\n        INSERT INTO platform.platform_setting (key, value, description, updated_by)\n        VALUES (:w, :wv, :wdesc, :actor), (:t, :tv, :tdesc, :actor), (:e, :ev, :edesc, :actor)\n        ON CONFLICT (key) DO UPDATE SET\n            value = EXCLUDED.value, description = EXCLUDED.description,\n            updated_by = EXCLUDED.updated_by, updated_at = now()\n    """),
        {
            "w": WINDOW_KEY,
            "wv": str(window),
            "wdesc": "Stock-cover average-sales window (days); D41 default 30.",
            "t": THRESHOLD_KEY,
            "tv": str(threshold),
            "tdesc": "Overstock alert threshold (days of cover); D41 default 180.",
            "e": EXPIRY_KEY,
            "ev": str(expiry),
            "edesc": "Expiry warning threshold (days before expiry); default 30.",
            "actor": str(actor_id),
        },
    )