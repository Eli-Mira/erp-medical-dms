"""Frontend wiring for the invoice desk.

The PWA is framework-free vanilla JS (D37), so these are static asset checks
plus served-asset checks: the screen is wired to the real endpoints, the totals
are labelled (client estimate vs server authority), and the posting safety gate
is respected rather than reimplemented.
"""
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

WEB = Path(__file__).resolve().parents[1] / "web"
client = TestClient(app)


def _read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def test_index_has_invoice_screen_controls():
    html = _read("index.html")
    for element_id in (
        "login-form", "login-username", "login-password", "login-submit",
        "invoice-form", "invoice-no", "invoice-date", "customer", "warehouse",
        "lines", "add-line", "save-draft", "form-error",
        "prev-grand", "draft-status", "draft-grand", "post-draft",
    ):
        assert f'id="{element_id}"' in html, element_id


def test_index_remains_rtl_and_registers_service_worker():
    html = _read("index.html")
    assert 'dir="rtl"' in html and 'lang="ar"' in html
    assert "serviceWorker" in html
    assert "app.js" in html and "styles.css" in html


def test_app_wires_master_data_and_invoice_endpoints():
    js = _read("app.js")
    for path in (
        "/auth/login", "/auth/me", "/auth/logout",
        "/master/branches", "/master/customers", "/master/products", "/master/warehouses",
        "/invoices",
    ):
        assert path in js, path


def test_totals_are_labelled_estimate_then_server_authority():
    html = _read("index.html")
    assert 'data-i18n="totals_title"' in html      # client estimate
    assert 'data-i18n="server_totals_title"' in html  # server authority


def test_posting_goes_through_the_guarded_endpoint():
    js = _read("app.js")
    # The UI calls the server's guarded /post route and surfaces its error; it
    # never sets the server flag or fabricates a status.
    assert "/post" in js
    assert "POSTING_ENABLED" not in js
    assert "posting_status" in js


def test_frontend_stays_framework_free():
    for name in ("index.html", "app.js", "styles.css"):
        text = _read(name)
        assert not re.search(r"\breact\b", text, re.IGNORECASE), name


def test_i18n_keys_match_and_cover_the_screen():
    ar = json.loads(_read("i18n/ar.json"))
    en = json.loads(_read("i18n/en.json"))
    assert set(ar) == set(en), "ar/en dictionaries must have identical keys"
    for key in (
        "new_invoice", "customer", "product", "quantity", "discount_pct",
        "grand_total", "save_draft", "status", "post_invoice",
        "totals_title", "server_totals_title",
        "err_customer", "err_invoice_no", "err_warehouse", "err_lines",
        "err_line_incomplete", "read_only_role",
        "status_draft", "status_posted", "status_voided",
    ):
        assert key in ar, key


def test_app_validates_incomplete_lines_and_read_only_role():
    js = _read("app.js")
    assert "incomplete" in js                 # half-filled lines are flagged, not dropped
    assert "err_line_incomplete" in js
    assert "read_only_auditor" in js          # create controls gated for the auditor


def test_app_never_injects_server_values_as_html():
    js = _read("app.js")
    # innerHTML is only ever used to clear a container, never to insert data.
    matches = re.findall(r"innerHTML\s*=\s*([^\s;]+)", js)
    assert matches and all(match in ('""', "''") for match in matches)


def test_assets_are_served_by_the_app():
    for path in ("/app/", "/app/app.js", "/app/styles.css", "/app/i18n/ar.json"):
        assert client.get(path).status_code == 200, path
