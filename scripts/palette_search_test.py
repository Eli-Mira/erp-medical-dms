"""P2.10 UI verification: command palette issues a server /search request and
renders the returned matches (desktop 1440x900 + mobile 390x844 emulation)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8018"
OUT = os.path.join(ROOT, "docs", "evidence", "invoice-cycle", "palette_search_20261020")
os.makedirs(OUT, exist_ok=True)

def run(viewport, label, mobile):
    calls, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport=viewport).new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: calls.append(r.url) if "/search?" in r.url else None)
        page.goto(f"{BASE}/app/", wait_until="networkidle")
        page.fill("#login-username", "demo_owner")
        page.fill("#login-password", "Demo-2026")
        page.click("#login-submit")
        page.wait_for_timeout(1500)
        page.click("#open-palette")
        page.fill("#palette-input", "DEMO-C03")
        page.wait_for_timeout(900)
        page.screenshot(path=os.path.join(OUT, f"{label}_palette_search.png"), full_page=True)
        rows = page.eval_on_selector_all("#palette-list li", "els => els.map(e => e.textContent.trim())")
        browser.close()
    return calls, rows, errors

for vp, label, mobile in [({"width":1440,"height":900},"desktop",False), ({"width":390,"height":844},"mobile",True)]:
    calls, rows, errs = run(vp, label, mobile)
    print(json.dumps({"label": label, "mobile_emulation": mobile,
                      "search_queries": [c.split("?")[1] for c in calls],
                      "results": rows[:4], "console_errors": errs}, ensure_ascii=True))
