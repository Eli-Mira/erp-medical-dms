"""Real browser -> shipped PWA -> real API -> independent persisted audit."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from browser_readiness import wait_for_held
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def live_app(tmp_path):
    assert os.environ.get("APP_ENV") == "test", "Use scripts/verify_invoice_cycle.py"
    target = make_url(os.environ["DATABASE_URL"])
    assert target.database and target.database.startswith("dms_cycle_test_")
    assert target.host in {"localhost", "127.0.0.1", "::1"}
    from app.db import engine

    assert engine.url == target
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == target.database
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log_path = tmp_path / "supplier-ui-server.log"
    with log_path.open("wb") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env={**os.environ, "APP_ENV": "test", "POSTING_ENABLED": "false"},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and proc.poll() is None:
                try:
                    with urllib.request.urlopen(
                        base + "/health", timeout=1
                    ) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.1)
            else:
                pytest.fail(
                    "Loopback server not ready: " + log_path.read_text(errors="replace")
                )
            yield base, engine
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            assert proc.poll() is not None
            print(f"supplier-ui server pid={proc.pid} exited={proc.returncode}")


def test_owner_supplier_create_pwa(live_app):
    base, engine = live_app
    from app.auth.repo import create_user

    username = "pwa_owner_" + uuid4().hex[:12]
    password = "Synthetic-Supplier-Test-2026!"
    with Session(engine) as seed:
        create_user(seed, username, password, role="owner", is_owner=True)
        seed.commit()
        owner_id = seed.scalar(
            text("SELECT id FROM platform.platform_user WHERE username=:u"),
            {"u": username},
        )
    code = "PWA-" + uuid4().hex[:12]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            # Fresh deterministic UI coverage, not offline/install acceptance.
            with browser.new_context(
                service_workers="block", viewport={"width": 1440, "height": 1000}
            ) as context:
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/app/", wait_until="domcontentloaded")
                expect(page.locator("#login-form")).to_be_visible()
                blocked_boot = []
                page.route(
                    "**/master/branches", lambda route: blocked_boot.append(route)
                )
                page.locator("#login-username").fill(username)
                page.locator("#login-password").fill(password)
                with (
                    page.expect_response(
                        lambda r: (
                            r.url.endswith("/auth/login") and r.request.method == "POST"
                        )
                    ) as login,
                    page.expect_request(base + "/master/branches"),
                ):
                    page.locator("#login-submit").click()
                assert login.value.status == 200
                nav = page.locator('[data-view="suppliers"]')
                expect(nav).to_be_visible()
                nav.click()
                expect(page.locator("#suppliers-view")).to_be_visible()
                wait_for_held(page, blocked_boot)
                assert len(blocked_boot) == 1
                blocked_boot[0].continue_()
                page.unroute("**/master/branches")
                expect(page.locator("#login-submit")).to_be_enabled()
                expect(page.locator("#suppliers-view")).to_be_visible()
                expect(page.locator("#supplier-add")).to_be_visible(timeout=3000)
                page.locator("#supplier-add").click()
                expect(page.locator("#supplier-dialog")).to_be_visible()
                page.locator("#supplier-code").fill(code)
                page.locator("#supplier-name-ar").fill("مورد اختبار المتصفح")
                page.locator("#supplier-name-en").fill("Synthetic Browser Supplier")
                page.locator("#supplier-phone").fill("01000000000")
                page.locator("#supplier-address").fill("Synthetic address")
                with page.expect_response(
                    lambda r: (
                        r.url.endswith("/master/suppliers")
                        and r.request.method == "POST"
                    )
                ) as created:
                    page.locator("#supplier-save").click()
                assert created.value.status == 201
                supplier = created.value.json()
                assert supplier["code"] == code
                expect(page.locator("#supplier-dialog")).not_to_be_visible()
                row = page.locator(
                    f'#supplier-rows tr[data-supplier-id="{supplier["id"]}"]'
                )
                expect(row).to_be_visible()
                expect(row).to_contain_text(code)
                expect(row).to_contain_text("مورد اختبار المتصفح")
                page.reload(wait_until="domcontentloaded")
                expect(page.locator("#home-view")).to_be_visible()
                page.locator('[data-view="suppliers"]').click()
                expect(row).to_be_visible()
                expect(row).to_contain_text(code)
                with Session(engine) as witness:
                    stored = (
                        witness.execute(
                            text(
                                "SELECT code,name_ar,name_en,contact_phone,address,is_active "
                                "FROM master_data.master_supplier WHERE id=:id"
                            ),
                            {"id": supplier["id"]},
                        )
                        .mappings()
                        .one()
                    )
                    assert dict(stored) == {
                        "code": code,
                        "name_ar": "مورد اختبار المتصفح",
                        "name_en": "Synthetic Browser Supplier",
                        "contact_phone": "01000000000",
                        "address": "Synthetic address",
                        "is_active": True,
                    }
                    actor = witness.scalar(
                        text(
                            "SELECT actor_user_id FROM audit.audit_log WHERE entity_type='master_supplier' "
                            "AND entity_id=:id AND action='created'"
                        ),
                        {"id": supplier["id"]},
                    )
                    assert actor == owner_id
                assert errors == []
        finally:
            browser.close()


@contextmanager
def _browser_user(live_app, role="owner", owner=True, lang="ar", width=1440):
    base, engine = live_app
    from app.auth.repo import create_user

    username = "pwa_user_" + uuid4().hex[:12]
    password = "Synthetic-Supplier-Test-2026!"
    with Session(engine) as seed:
        create_user(seed, username, password, role=role, is_owner=owner)
        seed.commit()
        user_id = seed.scalar(
            text("SELECT id FROM platform.platform_user WHERE username=:u"),
            {"u": username},
        )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            with browser.new_context(
                service_workers="block", viewport={"width": width, "height": 900}
            ) as context:
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/app/", wait_until="domcontentloaded")
                page.locator("#login-username").fill(username)
                page.locator("#login-password").fill(password)
                page.locator("#login-submit").click()
                expect(page.locator("#who-name")).to_have_text(username)
                if lang == "en":
                    page.locator("#lang").click()
                expect(page.locator("html")).to_have_attribute("lang", lang)
                expect(page.locator("html")).to_have_attribute(
                    "dir", "rtl" if lang == "ar" else "ltr"
                )
                _supplier_page(page, width)
                yield page, engine, user_id
                assert errors == []
        finally:
            browser.close()


def _supplier_page(page, width=1440):
    # Auth boot finishes its lookup requests by selecting Home and closing the drawer.
    expect(page.locator("#home-view")).to_be_visible()
    if (
        width < 1024
        and page.locator("#menu-toggle").get_attribute("aria-expanded") != "true"
    ):
        page.locator("#menu-toggle").click()
    expect(page.locator('[data-view="suppliers"]')).to_be_visible()
    page.locator('[data-view="suppliers"]').click()
    expect(page.locator("#suppliers-view")).to_be_visible()


def _create_from_browser(page):
    code = "PWA-" + uuid4().hex[:12]
    page.locator("#supplier-add").click()
    page.locator("#supplier-code").fill(code)
    page.locator("#supplier-name-ar").fill("مورد اختبار متكامل")
    page.locator("#supplier-name-en").fill("Synthetic supplier")
    page.locator("#supplier-phone").fill("01000000000")
    page.locator("#supplier-address").fill("Synthetic original address")
    with page.expect_response(
        lambda r: r.url.endswith("/master/suppliers") and r.request.method == "POST"
    ) as created:
        page.locator("#supplier-save").click()
    assert created.value.status == 201
    expect(page.locator("#supplier-dialog")).not_to_be_visible()
    data = created.value.json()
    expect(page.locator(f'tr[data-supplier-id="{data["id"]}"]')).to_be_visible()
    return data


@pytest.mark.parametrize(
    "lang,width",
    [("ar", 1440), ("en", 1440), ("ar", 390), ("en", 390)],
    ids=["ar-desktop", "en-desktop", "ar-mobile", "en-mobile"],
)
def test_owner_supplier_edit_deactivate_reactivate_pwa(live_app, lang, width, request):
    with _browser_user(live_app, lang=lang, width=width) as (page, engine, user_id):
        supplier = _create_from_browser(page)
        row = page.locator(f'tr[data-supplier-id="{supplier["id"]}"]')
        edit = row.locator("[data-supplier-edit]")
        expect(edit).to_be_visible(timeout=3000)
        edit.click()
        expect(page.locator("#supplier-dialog")).to_be_visible()
        expect(page.locator("#supplier-code")).to_have_value(supplier["code"])
        _capture_supplier_state(page, request, "edit-dialog")
        page.locator("#supplier-name-ar").fill("مورد تم تعديله")
        page.locator("#supplier-name-en").fill("")
        page.locator("#supplier-phone").fill("")
        page.locator("#supplier-address").fill("Synthetic updated address")
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/suppliers/" + supplier["id"])
                and r.request.method == "PATCH"
            )
        ) as updated:
            page.locator("#supplier-save").click()
        assert updated.value.status == 200
        expect(page.locator("#supplier-dialog")).not_to_be_visible()
        expect(row).to_contain_text("مورد تم تعديله")
        page.once("dialog", lambda dialog: dialog.accept())
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/suppliers/" + supplier["id"])
                and r.request.method == "DELETE"
            )
        ) as deleted:
            row.locator("[data-supplier-deactivate]").click()
        assert deleted.value.status == 204
        expect(row.locator("[data-supplier-reactivate]")).to_be_visible()
        page.reload(wait_until="domcontentloaded")
        _supplier_page(page, width)
        expect(row.locator("[data-supplier-reactivate]")).to_be_visible()
        with Session(engine) as witness:
            assert (
                witness.scalar(
                    text(
                        "SELECT is_active FROM master_data.master_supplier WHERE id=:id"
                    ),
                    {"id": supplier["id"]},
                )
                is False
            )
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/suppliers/" + supplier["id"])
                and r.request.method == "PATCH"
            )
        ) as restored:
            row.locator("[data-supplier-reactivate]").click()
        assert restored.value.status == 200
        expect(row.locator("[data-supplier-deactivate]")).to_be_visible()
        with Session(engine) as witness:
            stored = (
                witness.execute(
                    text(
                        "SELECT code,name_ar,name_en,contact_phone,address,is_active FROM master_data.master_supplier WHERE id=:id"
                    ),
                    {"id": supplier["id"]},
                )
                .mappings()
                .one()
            )
            assert dict(stored) == {
                "code": supplier["code"],
                "name_ar": "مورد تم تعديله",
                "name_en": None,
                "contact_phone": None,
                "address": "Synthetic updated address",
                "is_active": True,
            }
            audits = witness.execute(
                text(
                    "SELECT action,actor_user_id FROM audit.audit_log WHERE entity_type='master_supplier' AND entity_id=:id"
                ),
                {"id": supplier["id"]},
            ).all()
            assert sorted(a.action for a in audits) == [
                "created",
                "deactivated",
                "updated",
                "updated",
            ]
            assert all(a.actor_user_id == user_id for a in audits)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        _capture_supplier_state(page, request, "reactivated-list")


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize("width", [320, 390, 768, 1024, 1440])
def test_header_controls_remain_reachable_after_resize(live_app, lang, width, request):
    with _browser_user(live_app, lang=lang) as (page, _, _):
        page.set_viewport_size({"width": width, "height": 900})
        if width < 1024:
            # Resizing animates the closed drawer out from its desktop position.
            expect(page.locator("#sidebar")).not_to_be_in_viewport()
        else:
            expect(page.locator("#menu-toggle")).not_to_be_visible()
        layout = page.evaluate("""() => {
          const selectors = ['#open-palette', '#bell', '#logout', '#lang'];
          if (innerWidth < 1024) selectors.unshift('#menu-toggle');
          return {
            viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth,
            mobileSearch: matchMedia('(max-width: 900px)').matches,
            groups: [...document.querySelectorAll('.brand, .top-actions, #who, #offline-chip')].map(e => ({
              selector:e.id || e.className, width:e.getBoundingClientRect().width,
              display:getComputedStyle(e).display
            })),
            controls: selectors.map(selector => {
              const e = document.querySelector(selector), r = e.getBoundingClientRect();
              const c = getComputedStyle(e);
              const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
              return {selector, x:r.x, y:r.y, width:r.width, height:r.height,
                display:c.display, minWidth:c.minWidth, hit:e.contains(hit),
                inDrawer:!!(hit && hit.closest('#sidebar'))};
            })
          };
        }""")
        target = Path(request.config.option.xmlpath).with_name(
            request.node.name + ".json"
        )
        with target.open("x", encoding="utf-8") as evidence:
            json.dump(layout, evidence, ensure_ascii=False, indent=2)
        assert layout["scrollWidth"] <= layout["viewport"], layout
        assert all(control["hit"] for control in layout["controls"]), layout
        if width < 1024:
            page.locator("#menu-toggle").click()
            expect(page.locator("#menu-toggle")).to_have_attribute(
                "aria-expanded", "true"
            )
        page.locator('#sidebar [data-view="home"]').first.click()
        expect(page.locator("#home-view")).to_be_visible()
        expect(page.locator("#menu-toggle")).to_have_attribute("aria-expanded", "false")


def _capture_supplier_state(page, request, state):
    path = Path(request.config.option.xmlpath).parent / "screenshots"
    path.mkdir(exist_ok=True)
    target = path / (request.node.name + "--" + state + ".png")
    assert not target.exists(), "Evidence captures are append-only"
    page.wait_for_function("document.fonts.status === 'loaded'", timeout=10000)
    page.screenshot(path=str(target), full_page=True)


def test_supplier_save_is_single_flight_and_deactivation_can_be_cancelled(live_app):
    with _browser_user(live_app) as (page, engine, _):
        held = []

        def hold_post(route):
            if route.request.method == "POST":
                held.append(route)
            else:
                route.continue_()

        page.route("**/master/suppliers", hold_post)
        page.locator("#supplier-add").click()
        code = "BUSY-" + uuid4().hex[:12]
        page.locator("#supplier-code").fill(code)
        page.locator("#supplier-name-ar").fill("مورد اختبار منع التكرار")
        with page.expect_request(
            lambda r: r.url.endswith("/master/suppliers") and r.method == "POST"
        ):
            page.locator("#supplier-save").click()
        expect(page.locator("#supplier-save")).to_be_disabled()
        expect(page.locator("#supplier-cancel")).to_be_disabled()
        page.locator("#supplier-form").evaluate(
            "f => f.dispatchEvent(new Event('submit', {bubbles:true, cancelable:true}))"
        )
        page.keyboard.press("Escape")
        expect(page.locator("#supplier-dialog")).to_be_visible()
        wait_for_held(page, held)
        assert len(held) == 1
        with page.expect_response(
            lambda r: r.url.endswith("/master/suppliers") and r.request.method == "POST"
        ) as response:
            held[0].continue_()
        assert response.value.status == 201
        supplier = response.value.json()
        expect(page.locator("#supplier-dialog")).not_to_be_visible()
        page.once("dialog", lambda dialog: dialog.dismiss())
        page.locator(
            f'tr[data-supplier-id="{supplier["id"]}"] [data-supplier-deactivate]'
        ).click()
        with Session(engine) as witness:
            assert (
                witness.scalar(
                    text(
                        "SELECT is_active FROM master_data.master_supplier WHERE id=:id"
                    ),
                    {"id": supplier["id"]},
                )
                is True
            )
            assert (
                witness.scalar(
                    text(
                        "SELECT COUNT(*) FROM master_data.master_supplier WHERE code=:c"
                    ),
                    {"c": code},
                )
                == 1
            )
            assert (
                witness.scalar(
                    text(
                        "SELECT COUNT(*) FROM audit.audit_log WHERE entity_type='master_supplier' AND entity_id=:id"
                    ),
                    {"id": supplier["id"]},
                )
                == 1
            )


@pytest.mark.parametrize(
    "role,owner", [("finance", False), ("read_only_auditor", False), ("finance", True)]
)
def test_supplier_readers_have_no_mutation_controls(live_app, role, owner):
    with _browser_user(live_app, role=role, owner=owner) as (page, _, _):
        expect(page.locator("#supplier-add")).not_to_be_visible()
        expect(page.locator("#supplier-dialog")).not_to_be_visible()
        assert (
            page.locator(
                "[data-supplier-edit],[data-supplier-deactivate],[data-supplier-reactivate]"
            ).count()
            == 0
        )


def test_supplier_errors_keep_input_and_cancel_does_not_write(live_app):
    with _browser_user(live_app) as (page, engine, _):
        supplier = _create_from_browser(page)
        page.locator("#supplier-add").click()
        page.locator("#supplier-code").fill(supplier["code"])
        page.locator("#supplier-name-ar").fill("اسم يبقى عند التعارض")
        with page.expect_response(
            lambda r: r.url.endswith("/master/suppliers") and r.request.method == "POST"
        ) as duplicate:
            page.locator("#supplier-save").click()
        assert duplicate.value.status == 409
        expect(page.locator("#supplier-dialog-error")).to_be_visible()
        expect(page.locator("#supplier-name-ar")).to_have_value("اسم يبقى عند التعارض")
        expect(page.locator("#supplier-save")).to_be_enabled()
        page.locator("#supplier-code").fill("NEW-" + uuid4().hex[:12])
        page.locator("#supplier-name-ar").fill("   ")
        with page.expect_response(
            lambda r: r.url.endswith("/master/suppliers") and r.request.method == "POST"
        ) as invalid:
            page.locator("#supplier-save").click()
        assert invalid.value.status == 422
        expect(page.locator("#supplier-dialog-error")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#supplier-dialog")).not_to_be_visible()
        expect(page.locator("#supplier-add")).to_be_focused()
        with Session(engine) as witness:
            assert (
                witness.scalar(
                    text(
                        "SELECT COUNT(*) FROM audit.audit_log WHERE entity_type='master_supplier' AND entity_id=:id"
                    ),
                    {"id": supplier["id"]},
                )
                == 1
            )
