"""Invoice API integration tests: real PostgreSQL, no repository mocks."""
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.main import app


@pytest.fixture
def invoice_env():
    """Every request uses real SQL; API commits are contained in an outer rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode="create_savepoint")
    ids = {name: uuid4() for name in (
        "owner", "other", "branch", "territory", "other_territory", "customer", "other_customer",
        "warehouse", "product", "exempt", "batch", "reason",
    )}
    for role, uid, owner in [("owner", ids["owner"], True), ("medical_rep", ids["other"], False)]:
        db.execute(text("INSERT INTO platform.platform_user (id,username,password_hash,role,is_owner) VALUES (:id,:u,'unused',:role,:owner)"),
                   {"id": uid, "u": f"invoice_test_{uid.hex}", "role": role, "owner": owner})
    db.execute(text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:code,'Test branch')"), {"id": ids["branch"], "code": ids["branch"].hex[:20]})
    for key in ("territory", "other_territory"):
        db.execute(text("INSERT INTO master_data.master_territory(id,code,name_ar) VALUES (:id,:code,'Test territory')"), {"id": ids[key], "code": ids[key].hex[:20]})
    db.execute(text("INSERT INTO platform.user_territory(user_id,territory_id) VALUES (:uid,:tid)"), {"uid": ids["other"], "tid": ids["territory"]})
    for key, territory in [("customer", "territory"), ("other_customer", "other_territory")]:
        db.execute(text("INSERT INTO master_data.master_customer(id,code,name_ar,branch_id,territory_id) VALUES (:id,:code,'Test customer',:branch,:territory)"),
                   {"id": ids[key], "code": ids[key].hex[:30], "branch": ids["branch"], "territory": ids[territory]})
    db.execute(text("INSERT INTO master_data.master_warehouse(id,branch_id,code,name_ar) VALUES (:id,:branch,:code,'Test warehouse')"), {"id": ids["warehouse"], "branch": ids["branch"], "code": ids["warehouse"].hex[:30]})
    # Least privilege: the branch-scoped test caller may reference this warehouse
    # only through an explicit platform.user_branch grant to the owning branch.
    db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b) ON CONFLICT DO NOTHING"),
               {"u": ids["other"], "b": ids["branch"]})
    for key, rate in [("product", "14.00"), ("exempt", "0.00")]:
        db.execute(text("INSERT INTO master_data.master_product(id,sku,name_ar,base_price,vat_rate) VALUES (:id,:sku,'Test product',114,:rate)"), {"id": ids[key], "sku": ids[key].hex, "rate": rate})
    db.execute(text("INSERT INTO inventory.batch_record(id,product_id,warehouse_id,batch_no,expiry_date) VALUES (:id,:p,:w,'TEST',:expiry)"),
               {"id": ids["batch"], "p": ids["product"], "w": ids["warehouse"], "expiry": date.today() + timedelta(days=365)})
    db.execute(text("INSERT INTO audit.reason_code(id,code,category) VALUES (:id,:code,'void')"), {"id": ids["reason"], "code": ids["reason"].hex[:30]})
    db.commit()

    def get_test_db():
        yield db

    app.dependency_overrides[get_db] = get_test_db
    with TestClient(app) as client:
        def headers(user="owner"):
            sid = uuid4()
            db.execute(text("INSERT INTO platform.platform_session(id,user_id,expires_at) VALUES (:sid,:uid,now() + interval '1 hour')"), {"sid": sid, "uid": ids[user]})
            db.commit()
            return {"Authorization": f"Bearer {sid}"}

        payload = {
            "invoice_no": f"T-{uuid4().hex[:20]}", "branch_id": str(ids["branch"]),
            "warehouse_id": str(ids["warehouse"]), "customer_id": str(ids["customer"]),
            "invoice_date": date.today().isoformat(),
            "lines": [{"product_id": str(ids["product"]), "batch_id": str(ids["batch"]), "quantity": "2", "discount_pct": "0"}],
        }
        yield client, db, ids, payload, headers
    app.dependency_overrides.pop(get_db, None)
    db.close()
    transaction.rollback()
    connection.close()


def test_invoice_routes_require_authentication():
    with TestClient(app) as client:
        paths = [
            ("POST", "/invoices"),
            ("GET", "/invoices"),
            ("GET", "/invoices/00000000-0000-0000-0000-000000000001"),
            ("PUT", "/invoices/00000000-0000-0000-0000-000000000001"),
            ("POST", "/invoices/00000000-0000-0000-0000-000000000001/post"),
            ("POST", "/invoices/00000000-0000-0000-0000-000000000001/void"),
        ]
        for method, path in paths:
            response = client.request(method, path, json={})
            assert response.status_code == 401, (method, path, response.text)


def test_create_and_read_draft_snapshot_with_audit(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    response = client.post('/invoices', json=payload, headers=auth)
    assert response.status_code == 201, response.text
    invoice = response.json()
    assert invoice['posting_status'] == 'Draft'
    assert invoice['created_by'] == str(ids['owner'])
    assert invoice['territory_id'] == str(ids['territory'])
    assert invoice['version'] == 1
    assert invoice['grand_total'] == '228.00'
    assert invoice['vat_amount'] == '28.00'
    assert invoice['total_net'] == '200.00'
    assert invoice['lines'][0]['vat_rate'] == '14.00'
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).json() == invoice
    stored = db.execute(text('SELECT grand_total FROM sales.sales_invoice WHERE id=:id'), {'id': invoice['id']}).scalar_one()
    assert str(stored) == '228.00'
    event = db.execute(text("SELECT actor_user_id,action,new_values FROM audit.audit_log WHERE entity_type='sales_invoice' AND entity_id=:id"), {'id': invoice['id']}).one()
    assert event.actor_user_id == ids['owner']
    assert event.action == 'created'
    assert event.new_values['grand_total'] == '228.00'


def test_update_draft_increments_version_and_audits_old_and_new(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    invoice = client.post('/invoices', json=payload, headers=auth).json()
    payload['lines'][0]['quantity'] = '3'
    edit = {**payload, 'version': 1}
    response = client.put(f"/invoices/{invoice['id']}", json=edit, headers=auth)
    assert response.status_code == 200, response.text
    assert response.json()['version'] == 2
    assert response.json()['grand_total'] == '342.00'
    assert response.json()['updated_by'] == str(ids['owner'])
    event = db.execute(text("SELECT old_values,new_values FROM audit.audit_log WHERE action='modified' AND entity_id=:id"), {'id': invoice['id']}).one()
    assert event.old_values['grand_total'] == '228.00'
    assert event.new_values['grand_total'] == '342.00'
    stale = client.put(f"/invoices/{invoice['id']}", json=edit, headers=auth)
    assert stale.status_code == 409
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).json()['version'] == 2


def test_void_draft_preserves_lines_and_audits_reason(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    invoice = client.post('/invoices', json=payload, headers=auth).json()
    reason = {'version': 1, 'reason_id': str(ids['reason'])}
    response = client.post(f"/invoices/{invoice['id']}/void", json=reason, headers=auth)
    assert response.status_code == 200, response.text
    cancelled = response.json()
    assert cancelled['posting_status'] == 'Voided'
    assert cancelled['voided_by'] == str(ids['owner'])
    assert cancelled['void_reason_id'] == str(ids['reason'])
    assert cancelled['lines'] == invoice['lines']
    assert cancelled['posted_at'] is None
    assert cancelled['version'] == 2
    event = db.execute(text("SELECT action,new_values FROM audit.audit_log WHERE action='voided' AND entity_id=:id"), {'id': invoice['id']}).one()
    assert event.new_values['void_reason_id'] == str(ids['reason'])
    assert client.put(f"/invoices/{invoice['id']}", json={**payload, 'version': 2}, headers=auth).status_code == 409
    assert client.post(f"/invoices/{invoice['id']}/void", json={'version': 2, 'reason_id': str(ids['reason'])}, headers=auth).status_code == 409


@pytest.mark.parametrize('role', ['finance', 'sales_manager', 'district_manager', 'medical_rep'])
def test_assigned_business_roles_can_create_and_edit_own_drafts(invoice_env, role):
    client, db, ids, payload, headers = invoice_env
    db.execute(text('UPDATE platform.platform_user SET role=:role WHERE id=:id'), {'role': role, 'id': ids['other']})
    db.commit()
    auth = headers('other')
    response = client.post('/invoices', json=payload, headers=auth)
    assert response.status_code == 201, response.text
    invoice = response.json()
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).status_code == 200
    assert client.put(f"/invoices/{invoice['id']}", json={**payload, 'version': 1}, headers=auth).status_code == 200


@pytest.mark.parametrize('role', ['admin', 'warehouse_staff', 'read_only_auditor', 'user', 'unknown'])
def test_non_business_roles_cannot_create_or_edit_invoices(invoice_env, role):
    client, db, ids, payload, headers = invoice_env
    owner_auth = headers()
    invoice = client.post('/invoices', json=payload, headers=owner_auth).json()
    db.execute(text('UPDATE platform.platform_user SET role=:role WHERE id=:id'), {'role': role, 'id': ids['other']})
    db.commit()
    auth = headers('other')
    assert client.post('/invoices', json=payload, headers=auth).status_code == 403
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).status_code in {403, 404}
    assert client.put(f"/invoices/{invoice['id']}", json={**payload, 'version': 1}, headers=auth).status_code in {403, 404}
    assert client.post(f"/invoices/{invoice['id']}/void", json={'version': 1, 'reason_id': str(ids['reason'])}, headers=auth).status_code == 403
    assert client.post(f"/invoices/{invoice['id']}/post", headers=auth).status_code in {403, 404}


@pytest.mark.parametrize('role', ['finance', 'sales_manager', 'district_manager', 'medical_rep'])
def test_other_territory_and_unassigned_users_are_denied(invoice_env, role):
    client, db, ids, payload, headers = invoice_env
    db.execute(text('UPDATE platform.platform_user SET role=:role WHERE id=:id'), {'role': role, 'id': ids['other']})
    db.commit()
    payload['customer_id'] = str(ids['other_customer'])
    invoice = client.post('/invoices', json=payload, headers=headers()).json()
    auth = headers('other')
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).status_code == 404
    assert client.post('/invoices', json=payload, headers=auth).status_code == 404
    assert client.put(f"/invoices/{invoice['id']}", json={**payload, 'version': 1}, headers=auth).status_code == 404
    db.execute(text('DELETE FROM platform.user_territory WHERE user_id=:id'), {'id': ids['other']})
    db.commit()
    payload['customer_id'] = str(ids['customer'])
    assert client.post('/invoices', json=payload, headers=auth).status_code == 404


def test_medical_rep_cannot_read_or_edit_another_users_draft(invoice_env):
    client, db, ids, payload, headers = invoice_env
    invoice = client.post('/invoices', json=payload, headers=headers()).json()
    auth = headers('other')
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).status_code == 404
    assert client.put(f"/invoices/{invoice['id']}", json={**payload, 'version': 1}, headers=auth).status_code == 404


def test_revoked_session_user_is_rejected(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    db.execute(text('UPDATE platform.platform_user SET is_active=false WHERE id=:id'), {'id': ids['owner']})
    db.commit()
    assert client.get('/auth/me', headers=auth).status_code == 401
    assert client.post('/invoices', json=payload, headers=auth).status_code == 401


@pytest.mark.parametrize(('field', 'value'), [
    ('quantity', '0'), ('quantity', '-1'), ('quantity', '1.0001'),
    ('quantity', 'NaN'), ('quantity', 'Infinity'), ('quantity', True),
    ('discount_pct', '-1'), ('discount_pct', '100.01'),
    ('unit_price', '-1'), ('unit_price', '1.001'), ('unit_price', '10000000000'),
    ('vat_rate', '0'), ('line_total', '1'), ('net_price', '1'),
])
def test_invalid_or_server_owned_line_fields_rejected(invoice_env, field, value):
    client, db, ids, payload, headers = invoice_env
    payload['lines'][0][field] = value
    response = client.post('/invoices', json=payload, headers=headers())
    assert response.status_code == 422, response.text
    assert db.execute(text('SELECT count(*) FROM sales.sales_invoice WHERE invoice_no=:no'), {'no': payload['invoice_no']}).scalar_one() == 0


@pytest.mark.parametrize(('field', 'value'), [
    ('invoice_no', '   '), ('lines', []), ('posting_status', 'Posted'),
    ('grand_total', '0.01'), ('created_by', '00000000-0000-0000-0000-000000000001'),
    ('customer_id', 'bad-uuid'), ('invoice_date', 'not-a-date'),
])
def test_invalid_or_server_owned_header_fields_rejected(invoice_env, field, value):
    client, db, ids, payload, headers = invoice_env
    payload[field] = value
    assert client.post('/invoices', json=payload, headers=headers()).status_code == 422


def test_duplicate_number_returns_conflict_without_partial_lines_or_audits(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    first = client.post('/invoices', json=payload, headers=auth)
    assert first.status_code == 201
    duplicate = client.post('/invoices', json=payload, headers=auth)
    assert duplicate.status_code == 409, duplicate.text
    assert 'already exists' in duplicate.json()['detail']
    assert db.execute(text('SELECT count(*) FROM sales.sales_invoice WHERE invoice_no=:no'), {'no': payload['invoice_no']}).scalar_one() == 1
    assert db.execute(text('SELECT count(*) FROM sales.sales_invoice_line WHERE invoice_id=:id'), {'id': first.json()['id']}).scalar_one() == 1
    assert db.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_id=:id"), {'id': first.json()['id']}).scalar_one() == 1


@pytest.mark.parametrize('reference', ['customer_id', 'warehouse_id', 'product_id', 'batch_id'])
def test_unknown_references_rejected(invoice_env, reference):
    client, db, ids, payload, headers = invoice_env
    target = payload['lines'][0] if reference in {'product_id', 'batch_id'} else payload
    target[reference] = str(uuid4())
    # Warehouse is hidden as 404 (least privilege); other unknown references 422.
    expected = 404 if reference == 'warehouse_id' else 422
    assert client.post('/invoices', json=payload, headers=headers()).status_code == expected


def test_wrong_product_batch_and_expired_batch_rejected(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    payload['lines'][0]['product_id'] = str(ids['exempt'])
    assert client.post('/invoices', json=payload, headers=auth).status_code == 422
    payload['lines'][0]['product_id'] = str(ids['product'])
    db.execute(text('UPDATE inventory.batch_record SET expiry_date=:d WHERE id=:id'), {'d': date.today() - timedelta(days=1), 'id': ids['batch']})
    db.commit()
    assert client.post('/invoices', json=payload, headers=auth).status_code == 422


def test_product_vat_is_snapshotted_and_rates_are_not_client_controlled(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    payload['lines'].append({'product_id': str(ids['exempt']), 'quantity': '1', 'discount_pct': '0'})
    invoice = client.post('/invoices', json=payload, headers=auth).json()
    assert invoice['grand_total'] == '342.00'
    assert invoice['vat_amount'] == '28.00'
    assert [line['vat_rate'] for line in invoice['lines']] == ['14.00', '0.00']
    db.execute(text('UPDATE master_data.master_product SET vat_rate=5 WHERE id=:id'), {'id': ids['product']})
    db.commit()
    fetched = client.get(f"/invoices/{invoice['id']}", headers=auth).json()
    assert fetched['vat_amount'] == '28.00'
    assert fetched['lines'][0]['vat_rate'] == '14.00'
    updated = client.put(f"/invoices/{invoice['id']}", json={**payload, 'version': 1}, headers=auth)
    assert updated.status_code == 200, updated.text
    assert updated.json()['lines'][0]['vat_rate'] == '5.00'


def test_posting_blocked_by_api_and_database_with_no_success_audit(invoice_env):
    from sqlalchemy.exc import IntegrityError
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    invoice = client.post('/invoices', json=payload, headers=auth).json()
    response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    assert response.status_code == 409, response.text
    assert 'disabled' in response.json()['detail'].lower()
    assert client.get(f"/invoices/{invoice['id']}", headers=auth).json() == invoice
    with pytest.raises(IntegrityError) as rejected:
        with db.begin_nested():
            db.execute(text("UPDATE sales.sales_invoice SET posting_status='Posted' WHERE id=:id"), {'id': invoice['id']})
    assert rejected.value.orig.diag.constraint_name == 'ck_invoice_posted_at'
    assert db.execute(text("SELECT posting_status FROM sales.sales_invoice WHERE id=:id"), {'id': invoice['id']}).scalar_one() == 'Draft'
    assert db.execute(text("SELECT count(*) FROM audit.audit_log WHERE action='posted' AND entity_id=:id"), {'id': invoice['id']}).scalar_one() == 0


def test_audit_failure_rolls_back_entire_invoice(invoice_env, monkeypatch):
    from app.sales import router as invoice_router
    client, db, ids, payload, headers = invoice_env
    auth = headers()

    def audit_unavailable(*args, **kwargs):
        raise RuntimeError('Injected audit failure')

    monkeypatch.setattr(invoice_router, 'log_audit', audit_unavailable)
    with pytest.raises(RuntimeError, match='Injected audit failure'):
        client.post('/invoices', json=payload, headers=auth)
    assert db.execute(text('SELECT count(*) FROM sales.sales_invoice WHERE invoice_no=:no'), {'no': payload['invoice_no']}).scalar_one() == 0
    assert db.execute(text('SELECT count(*) FROM sales.sales_invoice_line WHERE product_id=:id'), {'id': ids['product']}).scalar_one() == 0


def test_void_requires_active_reason_and_medical_rep_cannot_void(invoice_env):
    client, db, ids, payload, headers = invoice_env
    rep_auth = headers('other')
    invoice = client.post('/invoices', json=payload, headers=rep_auth).json()
    reason = {'version': 1, 'reason_id': str(ids['reason'])}
    assert client.post(f"/invoices/{invoice['id']}/void", json=reason, headers=rep_auth).status_code == 403
    owner_auth = headers()
    db.execute(text('UPDATE audit.reason_code SET is_active=false WHERE id=:id'), {'id': ids['reason']})
    db.commit()
    assert client.post(f"/invoices/{invoice['id']}/void", json=reason, headers=owner_auth).status_code == 422
    assert client.get(f"/invoices/{invoice['id']}", headers=owner_auth).json()['posting_status'] == 'Draft'
