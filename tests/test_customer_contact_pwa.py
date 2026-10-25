"""Contact maintenance through the existing real bilingual PWA."""

from uuid import uuid4

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from test_customer_pwa import _browser_user, capture, customer_page, references
from test_supplier_pwa import live_app as live_app  # noqa: PLC0414


def seed_customer(
    engine,
    branch,
    territory,
    *,
    active=True,
    phone="010 1111 2222",
    address="العنوان السابق",
):
    cid = str(uuid4())
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO master_data.master_customer(id,code,name_ar,name_en,branch_id,territory_id,is_active,contact_phone,address) VALUES (:id,:code,:ar,:en,:b,:t,:active,:phone,:address)"
            ),
            {
                "id": cid,
                "code": "CONTACT-" + uuid4().hex[:12],
                "ar": "عميل بيانات الاتصال",
                "en": "Contact customer",
                "b": branch,
                "t": territory,
                "active": active,
                "phone": phone,
                "address": address,
            },
        )
    return cid


def persisted(engine, cid):
    with engine.connect() as db:
        row = dict(
            db.execute(
                text("SELECT * FROM master_data.master_customer WHERE id=:id"),
                {"id": cid},
            )
            .mappings()
            .one()
        )
        audits = [
            dict(r)
            for r in db.execute(
                text(
                    "SELECT * FROM audit.audit_log WHERE entity_type='master_customer' AND entity_id=:id AND action='updated'"
                ),
                {"id": cid},
            ).mappings()
        ]
    return row, audits


@pytest.mark.parametrize("lang", ["ar", "en"])
@pytest.mark.parametrize("width", [1440, 390])
def test_contact_edit_save_refresh_and_switch_records(live_app, lang, width, request):
    branch, territory = references(live_app[1])
    cid = seed_customer(live_app[1], branch, territory)
    other = seed_customer(
        live_app[1],
        branch,
        territory,
        phone="02 2222 3333",
        address="عنوان العميل الآخر",
    )
    initial, _ = persisted(live_app[1], cid)
    with _browser_user(live_app, lang=lang, width=width) as (page, engine, owner):
        customer_page(page, width)
        row = page.locator(f'tr[data-customer-id="{cid}"]')
        expect(row).to_contain_text("010 1111 2222")
        row.locator("[data-customer-edit]").click()
        expect(
            page.locator("#customer-dialog").get_by_label(
                "الهاتف" if lang == "ar" else "Phone", exact=True
            )
        ).to_have_value("010 1111 2222")
        expect(page.locator("#customer-address")).to_have_value("العنوان السابق")
        for field in ("code", "branch", "territory"):
            expect(page.locator("#customer-" + field)).to_be_disabled()
        assert page.locator("#customer-phone").get_attribute("dir") == "ltr"
        page.locator("#customer-phone").fill("010 9876-5432")
        page.locator("#customer-address").fill("١٢ شارع النيل\nالدور الثاني - القاهرة")
        capture(page, request, "editing-contacts")
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + cid)
                and r.request.method == "PATCH"
            )
        ) as saved:
            page.locator("#customer-save").click()
        assert saved.value.status == 200
        assert saved.value.request.post_data_json == {
            "contact_phone": "010 9876-5432",
            "address": "١٢ شارع النيل\nالدور الثاني - القاهرة",
        }
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        expect(row).to_contain_text("010 9876-5432")
        current, audits = persisted(engine, cid)
        assert current["contact_phone"] == "010 9876-5432"
        assert current["address"] == "١٢ شارع النيل\nالدور الثاني - القاهرة"
        assert {
            k: v for k, v in current.items() if k not in {"contact_phone", "address"}
        } == {k: v for k, v in initial.items() if k not in {"contact_phone", "address"}}
        assert len(audits) == 1 and audits[0]["actor_user_id"] == owner
        expect(page.locator(f'#customer option[value="{cid}"]')).to_have_count(1)
        page.locator(f'tr[data-customer-id="{other}"] [data-customer-edit]').click()
        expect(page.locator("#customer-phone")).to_have_value("02 2222 3333")
        expect(page.locator("#customer-address")).to_have_value("عنوان العميل الآخر")
        page.locator("#customer-cancel").click()
        row.locator("[data-customer-edit]").click()
        expect(page.locator("#customer-phone")).to_have_value("010 9876-5432")
        page.locator("#customer-save").click()
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        assert len(persisted(engine, cid)[1]) == 1
        page.reload(wait_until="domcontentloaded")
        expect(page.locator("#home-view")).to_be_visible()
        customer_page(page, width)
        row.locator("[data-customer-edit]").click()
        expect(page.locator("#customer-phone")).to_have_value("010 9876-5432")
        expect(page.locator("#customer-address")).to_have_value(
            "١٢ شارع النيل\nالدور الثاني - القاهرة"
        )
        capture(page, request, "persisted-after-refresh")
        page.locator("#customer-cancel").click()


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_contact_only_edit_preserves_legacy_blank_name(live_app, lang):
    branch, territory = references(live_app[1])
    cid = seed_customer(live_app[1], branch, territory)
    with live_app[1].begin() as db:
        db.execute(
            text("UPDATE master_data.master_customer SET name_en='' WHERE id=:id"),
            {"id": cid},
        )
    with _browser_user(live_app, lang=lang, width=390) as (page, engine, _owner):
        customer_page(page, 390)
        page.locator(f'tr[data-customer-id="{cid}"] [data-customer-edit]').click()
        page.locator("#customer-phone").fill("010 9999 8888")
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + cid)
                and r.request.method == "PATCH"
            )
        ) as saved:
            page.locator("#customer-save").click()
        assert saved.value.status == 200
        assert saved.value.request.post_data_json == {"contact_phone": "010 9999 8888"}
        assert persisted(engine, cid)[0]["name_en"] == ""


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_contact_clear_is_single_flight_and_persistent(live_app, lang):
    branch, territory = references(live_app[1])
    cid = seed_customer(live_app[1], branch, territory)
    with _browser_user(live_app, lang=lang, width=390) as (page, engine, _owner):
        customer_page(page, 390)
        page.locator(f'tr[data-customer-id="{cid}"] [data-customer-edit]').click()
        page.locator("#customer-phone").fill("")
        page.locator("#customer-address").fill("")
        held = []
        page.route(
            "**/master/customers/" + cid,
            lambda route: (
                held.append(route)
                if route.request.method == "PATCH"
                else route.continue_()
            ),
        )
        with page.expect_request(
            lambda r: r.url.endswith("/master/customers/" + cid) and r.method == "PATCH"
        ):
            page.locator("#customer-save").click()
        expect(page.locator("#customer-save")).to_be_disabled()
        page.locator("#customer-form").evaluate(
            "f => f.dispatchEvent(new Event('submit', {cancelable:true}))"
        )
        page.keyboard.press("Escape")
        expect(page.locator("#customer-dialog")).to_be_visible()
        assert len(held) == 1
        assert held[0].request.post_data_json == {
            "contact_phone": None,
            "address": None,
        }
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + cid)
                and r.request.method == "PATCH"
            )
        ) as saved:
            held[0].continue_()
        assert saved.value.status == 200
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        current, audits = persisted(engine, cid)
        assert current["contact_phone"] is None and current["address"] is None
        assert len(audits) == 1


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_contact_save_failure_keeps_input_and_allows_retry(live_app, lang):
    branch, territory = references(live_app[1])
    cid = seed_customer(live_app[1], branch, territory)
    before = persisted(live_app[1], cid)
    with _browser_user(live_app, lang=lang, width=390) as (page, engine, _owner):
        customer_page(page, 390)
        page.locator(f'tr[data-customer-id="{cid}"] [data-customer-edit]').click()
        page.locator("#customer-phone").fill("010 9999 0000")
        page.locator("#customer-name-ar").fill("")
        page.locator("#customer-save").click()
        assert page.locator("#customer-name-ar").evaluate(
            "e => e.validity.valueMissing"
        )
        assert persisted(engine, cid) == before
        page.locator("#customer-name-ar").fill(before[0]["name_ar"])
        assert page.locator("#customer-phone").get_attribute("maxlength") == "30"
        page.route(
            "**/master/customers/" + cid,
            lambda route: (
                route.fulfill(
                    status=503,
                    content_type="application/json",
                    body='{"detail":"Synthetic save failure"}',
                )
                if route.request.method == "PATCH"
                else route.continue_()
            ),
        )
        page.locator("#customer-save").click()
        expect(page.locator("#customer-dialog-error")).to_contain_text(
            "Synthetic save failure"
        )
        expect(page.locator("#customer-phone")).to_have_value("010 9999 0000")
        assert persisted(engine, cid) == before
        page.unroute("**/master/customers/" + cid)
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + cid)
                and r.request.method == "PATCH"
            )
        ) as saved:
            page.locator("#customer-save").click()
        assert saved.value.status == 200
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        assert persisted(engine, cid)[0]["contact_phone"] == "010 9999 0000"


@pytest.mark.parametrize("role", ["finance", "medical_rep", "read_only_auditor"])
@pytest.mark.parametrize("lang", ["ar", "en"])
def test_contact_readers_see_scoped_text_without_edit_controls(live_app, role, lang):
    branch, territory = references(live_app[1])
    address = '<img src=x onerror="window.contactLeak=true"> عنوان اختباري'
    cid = seed_customer(live_app[1], branch, territory, address=address)
    with _browser_user(live_app, role=role, owner=False, lang=lang, width=390) as (
        page,
        engine,
        user,
    ):
        with engine.begin() as db:
            db.execute(
                text(
                    "INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:u,:t)"
                ),
                {"u": user, "t": territory},
            )
        customer_page(page, 390)
        row = page.locator(f'tr[data-customer-id="{cid}"]')
        expect(row).to_contain_text("010 1111 2222")
        expect(row).to_contain_text(address)
        expect(row.locator("img")).to_have_count(0)
        assert page.evaluate("window.contactLeak === undefined")
        expect(page.locator("#customer-add")).not_to_be_visible()
        expect(
            page.locator(
                "[data-customer-edit], [data-customer-deactivate], [data-customer-reactivate]"
            )
        ).to_have_count(0)


def test_inactive_contact_edit_does_not_enable_new_sales(live_app):
    branch, territory = references(live_app[1])
    cid = seed_customer(live_app[1], branch, territory, active=False)
    with _browser_user(live_app) as (page, engine, _owner):
        customer_page(page, 1440)
        page.locator(f'tr[data-customer-id="{cid}"] [data-customer-edit]').click()
        page.locator("#customer-address").fill("عنوان محدث لعميل موقوف")
        with page.expect_response(
            lambda r: (
                r.url.endswith("/master/customers/" + cid)
                and r.request.method == "PATCH"
            )
        ) as saved:
            page.locator("#customer-save").click()
        assert saved.value.status == 200 and saved.value.json()["is_active"] is False
        expect(page.locator("#customer-dialog")).not_to_be_visible()
        expect(page.locator(f'#customer option[value="{cid}"]')).to_have_count(0)
        assert persisted(engine, cid)[0]["is_active"] is False
