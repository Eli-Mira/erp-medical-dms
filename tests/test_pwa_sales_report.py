"""Frontend wiring for the sales performance report screen.

Vanilla JS PWA (D37), so these are static asset checks plus served-asset
checks: the screen exists, is role-gated, consumes the real
GET /invoices/report endpoint, and keeps ar/en key parity.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

WEB = Path(__file__).resolve().parents[1] / "web"
client = TestClient(app)


def _read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def test_index_has_sales_report_screen_controls():
    html = _read("index.html")
    for element_id in (
        "salesreport-view",
        "salesreport-title",
        "salesreport-error",
        "sr-from",
        "sr-to",
        "sr-totals-rows",
        "sr-territory-rows",
        "sr-rep-rows",
        "sr-product-rows",
    ):
        assert f'id="{element_id}"' in html, element_id
    # The screen is explicitly labelled real server data, not a prototype.
    assert 'data-refresh="salesreport"' in html


def test_sales_report_nav_is_role_gated():
    html = _read("index.html")
    nav = [line for line in html.splitlines() if 'data-view="salesreport"' in line]
    assert nav, "sales report nav item missing"
    assert "data-roles" in nav[0]
    assert "medical_rep" in nav[0] and "read_only_auditor" in nav[0]


def test_app_wires_report_endpoint_and_view():
    js = _read("app.js")
    assert '"/invoices/report"' in js
    assert 'salesreport: "salesreport-view"' in js
    assert 'name === "salesreport"' in js
    assert "loadSalesReport" in js


def test_i18n_keys_cover_the_sales_report_screen():
    ar = json.loads(_read("i18n/ar.json"))
    en = json.loads(_read("i18n/en.json"))
    assert set(ar) == set(en), "ar/en dictionaries must have identical keys"
    for key in (
        "nav_salesreport",
        "salesreport_title",
        "salesreport_desc",
        "sr_by_territory",
        "sr_by_rep",
        "sr_by_product",
        "sr_empty",
        "rep",
        "invoices_count",
        "territory",
        "total_net",
        "vat_amount",
    ):
        assert key in ar, key
        assert ar[key].strip() and en[key].strip(), key


def test_pwa_serves_the_shell_with_report_screen():
    served = client.get("/app/index.html")
    assert served.status_code == 200
    assert "salesreport-view" in served.text


def test_every_section_is_hidden_by_view_switching():
    """hideAllSections() derives from REAL_VIEWS — every declared <section> must
    be a REAL_VIEWS target or a known container, or it would stay visible when
    another view opens (regression: targets stayed visible over salesreport).
    """
    import re

    js = _read("app.js")
    html = _read("index.html")
    real_views = dict(re.findall(r'(\w+):\s*"([\w-]+-view)"', js))
    covered = set(real_views.values()) | {"login-view", "draft-view", "module-view"}
    assert "salesreport-view" in covered
    sections = set(re.findall(r'<section id="([\w-]+-view)"', html))
    uncovered = sections - covered
    assert not uncovered, f"sections missing from REAL_VIEWS: {sorted(uncovered)}"
