"""Exercise real logout after populated transfer data; pending locks survive."""
from playwright.sync_api import expect


def verify(page, navigate, source, destination, product, batch, password, pending):
    navigate(page, "transfers")
    expect(page.locator("#transfer-save")).to_be_enabled()
    page.locator("#transfer-source").select_option(source)
    page.locator("#transfer-destination").select_option(destination)
    page.locator("#transfer-product").select_option(product)
    page.locator("#transfer-batch").select_option(batch)
    page.locator("#transfer-quantity").fill("1.125")
    private_note = "SYNTH-TRANSFER-SESSION-PRIVATE"
    page.locator("#transfer-note").fill(private_note)
    page.wait_for_function(
        'document.querySelector("#transfer-balance-rows").children.length >= 2'
    )
    assert page.locator("#transfer-rows tr").count() > 0
    if pending:
        page.evaluate("sessionStorage.setItem('transfer-pending', '1')")
    page.locator("#logout").click()
    expect(page.locator("#login-view")).to_be_visible()
    for name in ("source", "destination", "product", "batch"):
        assert page.locator("#transfer-" + name).evaluate("e => e.options.length") == 0
    assert page.locator("#transfer-quantity").input_value() == ""
    assert page.locator("#transfer-note").input_value() == ""
    assert page.locator("#transfer-rows tr").count() == 0
    assert page.locator("#transfer-balance-rows tr").count() == 0
    assert page.locator("#transfer-status").inner_text() == ""
    assert page.locator("#transfers-error").inner_text() == ""
    assert page.locator("#transfer-balance-error").inner_text() == ""
    expect(page.locator("#transfer-save")).to_be_disabled()
    assert page.evaluate("localStorage.getItem('token')") is None
    marker = page.evaluate("sessionStorage.getItem('transfer-pending')")
    assert marker == ("1" if pending else None)
    page.locator("#login-username").fill("fresh_beta_finance")
    page.locator("#login-password").fill(password)
    page.locator("#login-submit").click()
    expect(page.locator("#home-view")).to_be_visible()
    navigate(page, "transfers")
    if pending:
        expect(page.locator("#transfer-save")).to_be_disabled()
        assert page.evaluate("sessionStorage.getItem('transfer-pending')") == "1"
    else:
        expect(page.locator("#transfer-save")).to_be_enabled()
    assert page.locator("#transfer-note").input_value() == ""
    assert private_note not in page.locator("#transfers-view").inner_text()
