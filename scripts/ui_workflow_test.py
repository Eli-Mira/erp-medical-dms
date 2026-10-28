import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8018"
OUT = os.path.join(ROOT, "docs", "evidence", "invoice-cycle", "browser_test_20261019")
os.makedirs(OUT, exist_ok=True)
def shot(page, name): page.screenshot(path=os.path.join(OUT, name), full_page=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width":1440,"height":900})
    _msgs=[]
    page.on("console", lambda m: _msgs.append(m.type+": "+m.text))
    def _logresp(r):
        if "warehouses" in r.url or "invoices" in r.url:
            try: _msgs.append("WHRESP "+str(r.status)+" "+r.url+" :: "+r.text()[:200])
            except Exception as e: _msgs.append("WHERR "+str(e))
    page.on("response", _logresp)
    page.on("pageerror", lambda e: _msgs.append("PAGEERROR: "+str(e)))
    # Login
    page.goto(f"{BASE}/app/", wait_until="networkidle")
    page.fill("#login-username", "demo_owner")
    page.fill("#login-password", "Demo-2026")
    page.click("#login-submit")
    page.wait_for_timeout(1500)
    shot(page, "wf_01_login.png")
    # Navigate invoice desk
    page.locator('[data-view="invoice"]').first.scroll_into_view_if_needed()
    page.locator('[data-view="invoice"]').first.click()
    page.wait_for_timeout(1000)
    # Select first customer (DEMO-C01) by value via JS
    page.wait_for_timeout(1000)
    page.wait_for_timeout(1500)
    print("customer options:", page.locator("#customer option").count())
    cust_val = page.eval_on_selector("#customer", "el => el.options[1] ? el.options[1].value : ''")
    page.select_option("#customer", value=cust_val)
    whtxt = page.evaluate("async () => { const t=localStorage.getItem('token'); const r=await fetch('/master/warehouses', {headers:{Authorization:'Bearer '+t}}); return r.status+' :: '+(await r.text()).slice(0,120); }")
    print("WH FETCH:", whtxt)
    print("warehouse options:", page.locator("#warehouse option").count())
    print("warehouse innerHTML len:", len(page.locator("#warehouse").inner_html()))
    if page.locator("#warehouse option").count() > 1:
        page.select_option("#warehouse", index=1)
    # warehouse
    wh_opts = page.locator("#warehouse option").all_inner_texts()
    if wh_opts: page.select_option("#warehouse", index=1)
    # invoice no
    page.fill("#invoice-no", "DEMO-UI-1")
    page.fill("#invoice-date", "2026-10-19")
    # add line
    prod_sel = page.locator("[id^='line-product-']").first
    print("product options:", prod_sel.locator("option").count())
    opts = prod_sel.locator("option").all_inner_texts()
    print("product opts count:", len(opts))
    if len(opts) > 1:
        prod_sel.select_option(index=1)
        prod_sel.dispatch_event("change")
    qty_input = page.locator("[id^='line-qty-']").first
    qty_input.fill("2")
    qty_input.dispatch_event("input")
    page.wait_for_timeout(500)
    print("prev-grand:", page.locator("#prev-grand").inner_text())
    shot(page, "wf_02_draft_filled.png")
    # save draft
    print("customer val:", page.locator("#customer").input_value())
    print("warehouse val:", page.locator("#warehouse").input_value())
    print("invoice no:", page.locator("#invoice-no").input_value())
    print("qty val:", page.locator("[id^='line-qty-']").first.input_value())
    prodv = page.locator("[id^='line-product-']").first.input_value()
    print("product val:", prodv)
    page.click("#save-draft")
    page.wait_for_timeout(3000)
    fe = page.locator("#form-error")
    print("FORMERR count:", fe.count(), "textlen:", len(fe.inner_text()) if fe.count() else 0)
    open("formerr.txt","w",encoding="utf-8").write(fe.inner_text() if fe.count() else "NONE")
    print("DRAFT GRAND:", page.locator("#draft-grand").inner_text())
    # reopen via invoicelist
    page.locator('[data-view="invoicelist"]').first.scroll_into_view_if_needed()
    page.locator('[data-view="invoicelist"]').first.click()
    page.wait_for_timeout(2000)
    rows = page.locator("#invoice-rows tr").count()
    txt = page.locator("#invoice-rows").inner_text()
    print("INVOICELIST ROWS:", rows)
    open("docs/evidence/invoice-cycle/browser_test_20261019/_invoicelist.txt","w",encoding="utf-8").write(txt)
    print("DRAFT STATUS ELEM COUNT:", page.locator("#draft-status").count())
    print("BODY HAS Draft:", "Draft" in page.content())
    print("BODY HAS 422/400:", "422" in page.content() or "400" in page.content())
    print("DRAFT GRAND:", repr(page.locator("#draft-grand").inner_text() if page.locator("#draft-grand").count() else "NO_ELEM"))
    shot(page, "wf_03_saved.png")
    # reopen: navigate invoice list then open? Instead re-open same draft via URL not available; check status text
    status_text = page.locator("#draft-status").inner_text() if page.locator("#draft-status").count() else ""
    grand = page.locator("#draft-grand").inner_text() if page.locator("#draft-grand").count() else ""
    print("DRAFT STATUS:", status_text, "GRAND:", grand)
    # invoicelist
    page.locator('[data-view="invoicelist"]').first.scroll_into_view_if_needed()
    page.locator('[data-view="invoicelist"]').first.click()
    page.wait_for_timeout(1500)
    shot(page, "wf_04_invoicelist.png")
    # balances
    page.locator('[data-view="balances"]').first.scroll_into_view_if_needed()
    page.locator('[data-view="balances"]').first.click()
    page.wait_for_timeout(1500)
    shot(page, "wf_05_balances.png")
    # inventory stock
    page.locator('[data-view="inventory"]').first.scroll_into_view_if_needed()
    page.locator('[data-view="inventory"]').first.click()
    page.wait_for_timeout(1500)
    shot(page, "wf_06_inventory.png")
    # print emulation
    page.emulate_media(media="print")
    page.wait_for_timeout(300)
    shot(page, "wf_07_print_emulated.png")
    page.emulate_media(media="screen")
    # generate PDF of print view
    page.pdf(path=os.path.join(OUT, "wf_invoice_print.pdf"), format="A4", print_background=True)
    print("PDF generated")
    browser.close()
    import io; open("docs/evidence/invoice-cycle/browser_test_20261019/_msgs.txt","w",encoding="utf-8").write("\n".join(repr(m) for m in _msgs))
    print("DONE")
