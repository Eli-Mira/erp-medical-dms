import json
import re
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

WEB = Path(__file__).resolve().parents[1] / "web"
client = TestClient(app)

def test_rc2_01_module_title_and_role_gating():
    js_path = WEB / "app.js"
    js = js_path.read_text()
    assert 'el.moduleTitle = $("module-title")' in js
    assert 'if (el.moduleTitle)' in js
    role_ok_match = re.search(r'var ROLE_OK = \{[^}]*\}', js, re.DOTALL)
    assert role_ok_match
    role_ok_str = role_ok_match.group(0)
    for module in ['customers', 'products', 'warehouses']:
        mod_match = re.search(rf'{module}:\s*\[([^\]]+)\]', role_ok_str)
        if mod_match:
            roles = mod_match.group(1)
            assert '"warehouse_staff"' not in roles
            assert '"*"' not in roles
    doctors_match = re.search(r'doctors:\s*\[([^\]]+)\]', role_ok_str)
    assert doctors_match
    assert '"district_manager"' in doctors_match.group(1)
    audit_match = re.search(r'audit:\s*\[([^\]]+)\]', role_ok_str)
    assert audit_match
    assert '"read_only_auditor"' in audit_match.group(1)
    assert '.nav-item[data-view]' in js

def test_rc2_01_invoice_fefo_batch_picker_and_a11y():
    js_path = WEB / "app.js"
    js = js_path.read_text()
    assert 'async function loadLineBatches(' in js
    assert '/inventory/batches?warehouse_id=' in js
    assert 'Array.isArray(data)' in js
    assert 'expiry_date' in js
    assert 'batchSelect.dataset.role = "batch"' in js
    assert 'batchSelect.addEventListener("change"' in js
    assert 'el.warehouse.addEventListener("change"' in js
    inner_html_matches = re.findall(r'innerHTML\s*=\s*[^;]+;', js)
    for match in inner_html_matches:
        assert '""' in match or "''" in match
    html_path = WEB / "index.html"
    html = html_path.read_text()
    assert '<span data-i18n="batch_no">' in html
    table_wraps = re.findall(r'<div[^>]*class="table-wrap"[^>]*>', html)
    assert len(table_wraps) >= 31
    for wrap in table_wraps:
        assert 'tabindex="0"' in wrap
    css_path = WEB / "styles.css"
    css = css_path.read_text()
    assert re.search(r'--accent-700:\s*#0F766E', css)
    assert re.search(r'--text-muted:\s*#526075', css)
    assert re.search(r'--danger:\s*#B91C1C', css)
    assert 'font-variant-numeric: tabular-nums;' in css
    assert 'tabular-num;' not in css
    assert 'min-height: 44px' in css
    assert '#logout' in css
    sw_path = WEB / "sw.js"
    sw = sw_path.read_text()
    assert 'const CACHE = "medsys-shell-v20";' in sw
    ar_path = WEB / "i18n" / "ar.json"
    en_path = WEB / "i18n" / "en.json"
    ar = ar_path.read_text(encoding="utf-8")
    en = en_path.read_text(encoding="utf-8")
    ar_set = set(json.loads(ar).keys())
    en_set = set(json.loads(en).keys())
    assert ar_set == en_set
    assert 'batch_no' in ar
    assert 'transfer_no_batch' in ar
    response = client.get("/app/")
    assert response.status_code == 200
