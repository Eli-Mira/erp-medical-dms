"""R-35 click-through evidence for remaining REAL screens: targets, batches, cover,
audit, transfers, returns, marketing. Desktop 1440x900 + mobile 390x844 emulation."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8018"
OUT = os.path.join(ROOT, "docs", "evidence", "invoice-cycle", "r35_remaining_20261020")
os.makedirs(OUT, exist_ok=True)

VIEW_NAMES = ["targets", "batches", "cover", "audit", "transfers", "returns", "marketing"]

def shot(page, name):
    page.screenshot(path=os.path.join(OUT, name), full_page=True)

def open_drawer_if_mobile(page, mobile):
    if mobile:
        mt = page.locator("#menu-toggle")
        if mt.is_visible():
            mt.click()
            page.wait_for_timeout(500)

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
        shot(page, f"{label}_01_login.png")
        for view in VIEW_NAMES:
            open_drawer_if_mobile(page, mobile)
            loc = page.locator(f'[data-view="{view}"]').first
            loc.scroll_into_view_if_needed()
            loc.click()
            page.wait_for_timeout(1200)
            shot(page, f"{label}_{view}.png")
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
        shot(page, f"{label}_print_emulated.png")
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
