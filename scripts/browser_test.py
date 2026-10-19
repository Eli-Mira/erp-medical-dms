import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8018"
OUT = os.path.join(ROOT, "docs", "evidence", "invoice-cycle", "browser_test_20261019")
os.makedirs(OUT, exist_ok=True)

def shot(page, name):
    page.screenshot(path=os.path.join(OUT, name), full_page=True)

def nav(page, view, mobile):
    if mobile:
        # open drawer
        mt = page.locator("#menu-toggle")
        if mt.is_visible():
            mt.click()
            page.wait_for_timeout(300)
    loc = page.locator(f'[data-view="{view}"]').first
    loc.scroll_into_view_if_needed()
    loc.click(force=True)
    page.wait_for_timeout(800)

def run(viewport, label, mobile):
    errors = []
    overflow = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport=viewport)
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"PAGEERROR: {e}"))
        page.goto(f"{BASE}/app/", wait_until="networkidle")
        page.fill("#login-username", "demo_owner")
        page.fill("#login-password", "Demo-2026")
        page.click("#login-submit")
        page.wait_for_timeout(1500)
        shot(page, f"{label}_01_login_done.png")
        # customers
        nav(page, "customers", mobile)
        shot(page, f"{label}_02_customers.png")
        # invoicelist
        nav(page, "invoicelist", mobile)
        shot(page, f"{label}_03_invoicelist.png")
        # inventory
        nav(page, "inventory", mobile)
        shot(page, f"{label}_04_inventory.png")
        # balances
        nav(page, "balances", mobile)
        shot(page, f"{label}_05_balances.png")
        # invoice desk
        nav(page, "invoice", mobile)
        shot(page, f"{label}_06_invoice.png")
        pb = page.locator("#print-invoice")
        if pb.count() and pb.is_visible():
            pb.scroll_into_view_if_needed()
            pb.click(force=True)
            page.wait_for_timeout(500)
            shot(page, f"{label}_07_print.png")
        # overflow check
        overflow = page.evaluate("""() => {
            const vw = window.innerWidth;
            let bad = [];
            document.querySelectorAll('*').forEach(el => {
                if (el.closest('.sidebar:not(.open)')) return;
                const r = el.getBoundingClientRect();
                if (r.width === 0 && r.height === 0) return;
                if (r.right > vw + 2 || r.left < -2) bad.push((el.id||'') + '.' + String(el.className).split(' ')[0]);
            });
            return [...new Set(bad)].filter(x=>x.trim()).slice(0,20);
        }""")
        page.emulate_media(media="print")
        page.wait_for_timeout(300)
        shot(page, f"{label}_08_print_emulated.png")
        page.emulate_media(media="screen")
        browser.close()
        return errors, overflow

for vp, label, mobile in [({"width":1440,"height":900}, "desktop", False), ({"width":390,"height":844}, "mobile", True)]:
    errs, ov = run(vp, label, mobile)
    print(f"=== {label} {vp} (mobile_emulation={mobile}) ===")
    print("console errors:", len(errs))
    for e in errs: print("  ", e)
    print("overflow/clipped:", ov)
    print()
