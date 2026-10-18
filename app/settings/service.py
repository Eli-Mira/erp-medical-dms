"""Read/write the two approved inventory-policy settings (D41)."""

from uuid import UUID

from sqlalchemy import text

# D41-approved defaults; DB rows are the override, never hardcode in logic.
WINDOW_KEY = "stock_cover_window_days"
THRESHOLD_KEY = "overstock_threshold_days"
DEFAULT_WINDOW_DAYS = 30
DEFAULT_THRESHOLD_DAYS = 180

def read_policy(db):
    rows = db.execute(
        text("SELECT key, value FROM platform.platform_setting WHERE key IN (:w, :t)"),
        {"w": WINDOW_KEY, "t": THRESHOLD_KEY},
    ).mappings().all()
    values = {row["key"]: row["value"] for row in rows}
    try:
        window = int(values.get(WINDOW_KEY, DEFAULT_WINDOW_DAYS))
    except (TypeError, ValueError):
        window = DEFAULT_WINDOW_DAYS
    try:
        threshold = int(values.get(THRESHOLD_KEY, DEFAULT_THRESHOLD_DAYS))
    except (TypeError, ValueError):
        threshold = DEFAULT_THRESHOLD_DAYS
    return {"stock_cover_window_days": window, "overstock_threshold_days": threshold}

def write_policy(db, actor_id: UUID, window: int, threshold: int):
    db.execute(
        text("""
        INSERT INTO platform.platform_setting (key, value, description, updated_by)
        VALUES (:w, :wv, :wdesc, :actor), (:t, :tv, :tdesc, :actor)
        ON CONFLICT (key) DO UPDATE SET
            value = EXCLUDED.value, description = EXCLUDED.description,
            updated_by = EXCLUDED.updated_by, updated_at = now()
    """),
        {
            "w": WINDOW_KEY,
            "wv": str(window),
            "wdesc": "Stock-cover average-sales window (days); D41 default 30.",
            "t": THRESHOLD_KEY,
            "tv": str(threshold),
            "tdesc": "Overstock alert threshold (days of cover); D41 default 180.",
            "actor": str(actor_id),
        },
    )
