"""D40 UI verification: owner opens the private ledger, records one synthetic
entry, and sees it in the table. Desktop 1440x900 + mobile 390x844 emulation."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8018"
OUT = os.path.join(ROOT, "docs", "evidence", "invoice-cycle", "private_accounts_ui_20261020")
os.makedirs(OUT, exist_ok=True)


def run(viewport, label, mobile):
    errors, statuses = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(viewport=viewport).new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("response", lambda r: statuses.append((r.request.method, r.url, r.status))
                if "/private-accounts" in r.url else None)
        page.goto(f"{BASE}/app/", wait_until="networkidle")
        page.fill("#login-username", "demo_owner")
        page.fill("#login-password", "Demo-2026")
        page.click("#login-submit")
        page.wait_for_timeout(1500)
        if mobile:
            page.click("#menu-toggle")
            page.wait_for_timeout(400)
        page.click('[data-view="privateaccounts"]')
        page.wait_for_timeout(900)
        page.screenshot(path=os.path.join(OUT, f"{label}_private_list.png"), full_page=True)
        before = page.eval_on_selector_all("#private-rows tr", "els => els.length")
        page.fill("#private-label", "UI test account")
        page.fill("#private-date", "2026-10-20")
        page.fill("#private-credit", "1250.50")
        page.fill("#private-note", "synthetic UI verification")
        page.click("#private-save")
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(OUT, f"{label}_private_saved.png"), full_page=True)
        rows = page.eval_on_selector_all(
            "#private-rows tr", "els => els.map(e => e.textContent.replace(/\\s+/g,' ').trim())")
        notice = page.text_content("#private-notice")
        total_credit = page.text_content("#private-credit-total")
        browser.close()
    return {"before": before, "rows": rows[:3], "notice": notice,
            "credit_total": total_credit, "calls": statuses, "console_errors": errors}


for vp, label, mobile in [({"width": 1440, "height": 900}, "desktop", False),
                          ({"width": 390, "height": 844}, "mobile", True)]:
    result = run(vp, label, mobile)
    result["label"] = label
    result["mobile_emulation"] = mobile
    print(json.dumps(result, ensure_ascii=True))

# Remove only the rows this script created, so the demo ledger stays clean.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://dms:dms-dev@localhost:5432/medical_demo")
from sqlalchemy import create_engine, text as sql_text
engine = create_engine(os.environ["DATABASE_URL"])
with engine.begin() as conn:
    removed = conn.execute(sql_text(
        "DELETE FROM private.account_entry WHERE account_label = 'UI test account'"
    )).rowcount
print(json.dumps({"cleanup_removed_rows": removed}, ensure_ascii=True))
