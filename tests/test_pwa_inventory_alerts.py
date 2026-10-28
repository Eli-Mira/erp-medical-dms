"""Frontend wiring for the REAL inventory alerts screen (overstock + cover).

Vanilla JS PWA (D37); static asset + served-asset checks. The screen consumes
the approved GET /inventory/cover and GET /settings/inventory-policy
endpoints; the only alert rule is the approved overstock threshold — no
low-stock threshold is invented anywhere.
"""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

WEB = Path(__file__).resolve().parents[1] / "web"
ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def _read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def test_index_has_inventory_alerts_screen_controls():
    html = _read("index.html")
    for element_id in (
        "inventoryalerts-view",
        "inventoryalerts-title",
        "invalerts-error",
        "invalerts-policy",
        "invalerts-status",
        "invalerts-sort",
        "invalerts-search",
        "invalerts-rows",
    ):
        assert f'id="{element_id}"' in html, element_id
    assert 'data-refresh="inventoryalerts"' in html


def test_alerts_nav_mirrors_backend_read_roles():
    html = _read("index.html")
    nav = [line for line in html.splitlines() if 'data-view="inventoryalerts"' in line]
    assert nav, "inventory alerts nav item missing"
    for role in (
        "owner",
        "finance",
        "warehouse_staff",
        "sales_manager",
        "district_manager",
        "read_only_auditor",
    ):
        assert role in nav[0], role


def test_app_wires_alerts_view_endpoints_and_honest_states():
    js = _read("app.js")
    assert 'inventoryalerts: "inventoryalerts-view"' in js
    assert 'name === "inventoryalerts"' in js
    assert "loadInventoryAlerts" in js
    loader = js[
        js.index("function loadInventoryAlerts") : js.index("function loadAudit")
    ]
    assert '"/inventory/cover"' in loader
    assert '"/settings/inventory-policy"' in loader
    # honest no-sales-history rendering, not a fabricated value
    assert "no_sales_history" in loader


def test_policy_knobs_stay_exactly_the_approved_pair():
    """30-day window / 180-day overstock (D41); no invented low-stock rule."""
    service = (ROOT / "app" / "settings" / "service.py").read_text(encoding="utf-8")
    assert "DEFAULT_WINDOW_DAYS = 30" in service
    assert "DEFAULT_THRESHOLD_DAYS = 180" in service
    schemas = (ROOT / "app" / "settings" / "schemas.py").read_text(encoding="utf-8")
    assert (
        "stock_cover_window_days" in schemas and "overstock_threshold_days" in schemas
    )
    for source in (ROOT / "app").rglob("*.py"):
        assert "low_stock" not in source.read_text(encoding="utf-8").lower(), source


def test_i18n_keys_cover_inventory_alerts_screen():
    ar = json.loads(_read("i18n/ar.json"))
    en = json.loads(_read("i18n/en.json"))
    assert set(ar) == set(en), "ar/en dictionaries must have identical keys"
    for key in (
        "nav_inventoryalerts",
        "invalerts_title",
        "invalerts_desc",
        "invalerts_policy_window",
        "invalerts_policy_threshold",
        "invalerts_status_filter",
        "invalerts_overstock",
        "invalerts_all",
        "invalerts_no_history",
        "invalerts_sort",
        "invalerts_sort_cover_desc",
        "invalerts_sort_cover_asc",
        "invalerts_sort_onhand_desc",
        "invalerts_search",
        "invalerts_avg_daily",
        "invalerts_empty",
        "invalerts_st_overstock",
        "invalerts_st_ok",
        "invalerts_st_nohist",
    ):
        assert key in ar, key
        assert ar[key].strip() and en[key].strip(), key


def test_pwa_serves_the_shell_with_alerts_screen():
    served = client.get("/app/index.html")
    assert served.status_code == 200
    assert "inventoryalerts-view" in served.text


def test_alerts_section_registered_in_real_views():
    """The generic REAL_VIEWS derivation test lives with the salesreport slice;
    this re-checks the section naming contract for the alerts screen.
    """
    js = _read("app.js")
    html = _read("index.html")
    real_views = dict(re.findall(r'(\w+):\s*"([\w-]+-view)"', js))
    assert real_views.get("inventoryalerts") == "inventoryalerts-view"
    sections = set(re.findall(r'<section id="([\w-]+-view)"', html))
    assert "inventoryalerts-view" in sections


def test_management_summary_screen_wired_to_report_endpoint():
    html = _read("index.html")
    for element_id in (
        "mgmtsummary-view",
        "mgmtsummary-title",
        "mgmtsummary-error",
        "ms-date",
        "mgmtsummary-rows",
        "ms-alerts",
        "ms-kpi-sales",
        "ms-kpi-collections",
        "ms-kpi-ar",
        "ms-kpi-overstock",
    ):
        assert f'id="{element_id}"' in html, element_id
    nav = [line for line in html.splitlines() if 'data-view="mgmtsummary"' in line]
    assert nav and "data-roles" in nav[0]
    # reps/warehouse staff have no management-summary role (backend 403).
    for role in ("medical_rep", "warehouse_staff"):
        assert role not in nav[0], role
    js = _read("app.js")
    assert 'mgmtsummary: "mgmtsummary-view"' in js
    assert '"/reports/management-summary"' in js
    assert "loadManagementSummary" in js
