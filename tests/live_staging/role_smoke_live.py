"""Opt-in, serial live-staging browser smoke; no database imports or seeding.

Explicit selector (filename deliberately excluded from ordinary test discovery):
  pytest --confcutdir=tests/live_staging tests/live_staging/role_smoke_live.py -v -s

Parent-owned runtime interface:
  BASE_URL: staging origin only (no credentials, query, fragment or path)
  ERP_STAGING_SYNTHETIC_ONLY=1: parent attests this is disposable synthetic staging
  ERP_STAGING_PASSWORD: generated runtime password shared by these synthetic users
  ERP_STAGING_USER_<ROLE>: optional username override; default demo_<role>
  ERP_STAGING_PRODUCT_ID, ERP_STAGING_PRODUCT_SKU: active synthetic catalog fixture
  ERP_STAGING_WAREHOUSE_ID: active warehouse with positive stock of that product

Parent seeds the six active users, owner.is_owner=True and others.is_owner=False,
with explicit platform.user_branch grants to the fixture warehouse's owning branch.
Do not substitute branch_warehouse routing for branch grants. No territory grant is
needed by the selected product/stock reads. Parent alone seeds and executes serially.
The confcutdir flag avoids tests/conftest.py's eager app/database imports.

Non-owner denial: GET /auth/users -> 403 {'detail': 'owner-only'}, a real
owner-administration READ authorization denial (not a mutation or validation probe).
Owner has no role-denied route in this matrix. Its explicit universal invariant is
GET /auth/me with the just-revoked session -> 401 {'detail': 'session expired'}.
This is authentication/session-revocation denial, NOT RBAC or audit immutability.
No financial mutation, credential file, screenshot, trace, token or response-body log.
"""

import json
import os
import re
from urllib.parse import urlencode, urlsplit
from uuid import UUID

import pytest
from playwright.sync_api import expect, sync_playwright

ROLES = (
    "owner",
    "finance",
    "sales_manager",
    "warehouse_staff",
    "medical_rep",
    "read_only_auditor",
)


def _required(name):
    value = os.environ.get(name)
    if not value:
        pytest.fail("Missing required staging environment variable: " + name, pytrace=False)
    return value


@pytest.fixture(scope="module")
def staging_contract():
    assert _required("ERP_STAGING_SYNTHETIC_ONLY") == "1", "Synthetic staging attestation required"
    base = _required("BASE_URL").rstrip("/")
    target = urlsplit(base)
    assert (
        target.scheme in {"http", "https"}
        and target.hostname
        and target.username is None
        and target.password is None
        and not target.path
        and not target.query
        and not target.fragment
    ), "BASE_URL must be a credential-free staging origin"
    _required("ERP_STAGING_PASSWORD")
    return {
        "base": base,
        "product": str(UUID(_required("ERP_STAGING_PRODUCT_ID"))),
        "sku": _required("ERP_STAGING_PRODUCT_SKU"),
        "warehouse": str(UUID(_required("ERP_STAGING_WAREHOUSE_ID"))),
    }


def _record(role, lang, action, method, path, status, expected, kind):
    # Fixed metadata only: never append exceptions, headers, bodies or credentials.
    print(
        json.dumps(
            {
                "case": "live_staging_role_smoke",
                "role": role,
                "lang": lang,
                "action": action,
                "method": method,
                "path": path,
                "status": status,
                "expected_status": expected,
                "kind": kind,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _read(page, path, *, role, lang, kind, product=None, warehouse=None, sku=None):
    # Real browser HTTP, with only sanitized predicates crossing into pytest output.
    result = page.evaluate(
        """async ({path, product, warehouse, sku}) => {
          const response = await fetch(path, {
            headers: {Authorization: 'Bearer ' + localStorage.getItem('token')},
            signal: AbortSignal.timeout(10000),
          });
          const body = await response.json();
          return {
            status: response.status,
            matched: Array.isArray(body) && body.some(row =>
              (warehouse ? row.product_id === product && row.warehouse_id === warehouse &&
                           Number(row.quantity) > 0 : row.id === product && row.sku === sku)),
            denied: body.detail === 'owner-only',
          };
        }""",
        {"path": path, "product": product, "warehouse": warehouse, "sku": sku},
    )
    expected = 403 if kind == "rbac_owner_only_read" else 200
    _record(role, lang, "denied_read" if expected == 403 else "permitted_read", "GET", path.split("?")[0], result["status"], expected, kind)
    assert result["status"] == expected, "Unexpected HTTP status; see sanitized case record"
    if expected == 403:
        assert result["denied"], "Expected the route's owner-only authorization guard"
    else:
        assert result["matched"], "Required synthetic fixture missing from authorized read"


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_live_staging_role_read_denial_and_direction(staging_contract, role, lang):
    contract = staging_contract
    username = os.environ.get("ERP_STAGING_USER_" + role.upper(), "demo_" + role)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with browser.new_context(
                service_workers="block", viewport={"width": 1440, "height": 900}
            ) as context:
                page = context.new_page()
                page.set_default_timeout(10000)
                page.goto(contract["base"] + "/app/", wait_until="domcontentloaded")
                page.locator("#login-username").fill(username)
                page.locator("#login-password").fill(_required("ERP_STAGING_PASSWORD"))
                with page.expect_response(
                    lambda r: r.url == contract["base"] + "/auth/login"
                    and r.request.method == "POST"
                ) as login:
                    page.locator("#login-submit").click()
                _record(role, lang, "browser_login", "POST", "/auth/login", login.value.status, 200, "authentication")
                assert login.value.status == 200, "Browser login failed; response body deliberately withheld"
                expect(page.locator("#home-view")).to_be_visible()
                identity = page.evaluate(
                    """async ({role, username}) => {
                      const r = await fetch('/auth/me', {
                        headers: {Authorization: 'Bearer ' + localStorage.getItem('token')},
                        signal: AbortSignal.timeout(10000),
                      });
                      const body = await r.json();
                      return {status: r.status, matched: body.role === role &&
                        body.username === username && body.is_owner === (role === 'owner')};
                    }""",
                    {"role": role, "username": username},
                )
                _record(role, lang, "identity", "GET", "/auth/me", identity["status"], 200, "authentication")
                assert identity == {"status": 200, "matched": True}, "Synthetic account identity mismatch"
                expect(page.locator("html")).to_have_attribute("lang", re.compile("^(ar|en)$"))
                if page.locator("html").get_attribute("lang") != lang:
                    page.locator("#lang").click()
                expect(page.locator("html")).to_have_attribute("lang", lang)
                expect(page.locator("html")).to_have_attribute("dir", "rtl" if lang == "ar" else "ltr")
                _record(role, lang, "direction", "DOM", "html", 1, 1, "rtl" if lang == "ar" else "ltr")

                if role == "warehouse_staff":
                    _read(
                        page,
                        "/inventory/stock?warehouse_id=" + contract["warehouse"] + "&product_id=" + contract["product"],
                        role=role, lang=lang, kind="branch_scoped_stock_read",
                        product=contract["product"], warehouse=contract["warehouse"],
                    )
                else:
                    # q is encoded by the platform, never concatenated into a query.
                    _read(
                        page, "/master/products?" + urlencode({"q": contract["sku"]}),
                        role=role, lang=lang, kind="catalog_read",
                        product=contract["product"], sku=contract["sku"],
                    )
                if role != "owner":
                    _read(page, "/auth/users", role=role, lang=lang, kind="rbac_owner_only_read")

                # Keep the old token inside the browser; do not return it to Python.
                page.evaluate("window.__smokeRevokedToken = localStorage.getItem('token')")
                with page.expect_response(
                    lambda r: r.url == contract["base"] + "/auth/logout"
                    and r.request.method == "POST"
                ) as logout:
                    page.locator("#logout").click()
                _record(role, lang, "logout", "POST", "/auth/logout", logout.value.status, 200, "session_revocation")
                assert logout.value.status == 200
                expect(page.locator("#login-view")).to_be_visible()
                assert page.evaluate("localStorage.getItem('token')") is None
                revoked = page.evaluate(
                    """async () => {
                      const token = window.__smokeRevokedToken;
                      delete window.__smokeRevokedToken;
                      const r = await fetch('/auth/me', {
                        headers: {Authorization: 'Bearer ' + token},
                        signal: AbortSignal.timeout(10000),
                      });
                      const body = await r.json();
                      return {status: r.status, denied: body.detail === 'session expired'};
                    }"""
                )
                _record(role, lang, "denied_revoked_session_read", "GET", "/auth/me", revoked["status"], 401, "universal_session_invariant_NOT_RBAC")
                assert revoked == {"status": 401, "denied": True}, "Revoked session retained access"
                print("ASSERTION_REACHED live_staging_role_smoke " + role + " " + lang, flush=True)
        finally:
            browser.close()
