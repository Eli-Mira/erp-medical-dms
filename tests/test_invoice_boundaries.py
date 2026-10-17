"""Boundary controls beyond the main real-Postgres draft-flow tests."""
from uuid import uuid4

import pytest
from sqlalchemy import text

pytest_plugins = ["test_invoice_api"]  # Reuse its real-Postgres fixture, not its test cases.


def test_price_override_requires_finance_or_owner(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers('other')
    payload['lines'][0]['unit_price'] = '100.00'
    assert client.post('/invoices', json=payload, headers=auth).status_code == 403
    db.execute(text("UPDATE platform.platform_user SET role='finance' WHERE id=:id"), {'id': ids['other']})
    db.commit()
    created = client.post('/invoices', json=payload, headers=auth)
    assert created.status_code == 201, created.text
    assert created.json()['lines'][0]['unit_price'] == '100.00'


def test_sales_manager_can_void_assigned_territory_draft(invoice_env):
    client, db, ids, payload, headers = invoice_env
    invoice = client.post('/invoices', json=payload, headers=headers()).json()
    db.execute(text("UPDATE platform.platform_user SET role='sales_manager' WHERE id=:id"), {'id': ids['other']})
    db.commit()
    response = client.post(f"/invoices/{invoice['id']}/void", json={'version': 1, 'reason_id': str(ids['reason'])}, headers=headers('other'))
    assert response.status_code == 200, response.text
    assert response.json()['voided_by'] == str(ids['other'])


def test_owner_label_without_owner_flag_cannot_elevate_access(invoice_env):
    client, db, ids, payload, headers = invoice_env
    db.execute(text("UPDATE platform.platform_user SET role='owner' WHERE id=:id"), {'id': ids['other']})
    db.commit()
    assert client.post('/invoices', json=payload, headers=headers('other')).status_code == 403


@pytest.mark.parametrize('reference', ['customer', 'product', 'warehouse'])
def test_inactive_reference_rejected(invoice_env, reference):
    client, db, ids, payload, headers = invoice_env
    # All identifiers in this SQL are fixed test-owned names, not API input.
    table = {'customer': 'master_customer', 'product': 'master_product', 'warehouse': 'master_warehouse'}[reference]
    db.execute(text(f'UPDATE master_data.{table} SET is_active=false WHERE id=:id'), {'id': ids[reference]})
    db.commit()
    assert client.post('/invoices', json=payload, headers=headers()).status_code == 422


def test_cross_branch_reference_rejected(invoice_env):
    client, db, ids, payload, headers = invoice_env
    payload['branch_id'] = str(uuid4())
    assert client.post('/invoices', json=payload, headers=headers()).status_code == 422


def test_invoice_total_overflow_rejected_before_persistence(invoice_env):
    client, db, ids, payload, headers = invoice_env
    payload['lines'][0].update(quantity='999999999.999', unit_price='9999999999.99')
    response = client.post('/invoices', json=payload, headers=headers())
    assert response.status_code == 422, response.text
    assert db.execute(text('SELECT count(*) FROM sales.sales_invoice WHERE invoice_no=:no'), {'no': payload['invoice_no']}).scalar_one() == 0


def test_update_audit_failure_preserves_original_header_lines_and_version(invoice_env, monkeypatch):
    from app.sales import router
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    original = client.post('/invoices', json=payload, headers=auth).json()
    payload['lines'][0]['quantity'] = '4'

    def fail_audit(*args, **kwargs):
        raise RuntimeError('Injected update audit failure')

    monkeypatch.setattr(router, 'log_audit', fail_audit)
    with pytest.raises(RuntimeError, match='Injected update audit failure'):
        client.put(f"/invoices/{original['id']}", json={**payload, 'version': 1}, headers=auth)
    assert client.get(f"/invoices/{original['id']}", headers=auth).json() == original


def test_duplicate_number_on_update_keeps_original_invoice(invoice_env):
    client, db, ids, payload, headers = invoice_env
    auth = headers()
    first = client.post('/invoices', json=payload, headers=auth).json()
    payload['invoice_no'] += '-2'
    second = client.post('/invoices', json=payload, headers=auth).json()
    payload['invoice_no'] = first['invoice_no']
    response = client.put(f"/invoices/{second['id']}", json={**payload, 'version': 1}, headers=auth)
    assert response.status_code == 409, response.text
    assert client.get(f"/invoices/{second['id']}", headers=auth).json() == second
