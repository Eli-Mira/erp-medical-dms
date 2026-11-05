"""Owner order: assigned-warehouse lookup only; warehouse_staff cannot write."""
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_inventory_api import stock_env as stock_env  # noqa: PLC0414
from test_lane1_r22_territory_http import (
    require_owned_verifier_database as require_owned_verifier_database,  # noqa: PLC0414
)


@pytest.fixture
def assigned_stock(stock_env):
    client, db, ids, headers, movement = stock_env
    foreign_branch = uuid4()
    db.execute(text("INSERT INTO master_data.master_branch(id,code,name_ar) VALUES (:id,:c,'Foreign stock branch')"), {"id": foreign_branch, "c": foreign_branch.hex[:20]})
    db.execute(text("UPDATE master_data.master_warehouse SET branch_id=:b WHERE id=:w"), {"b": foreign_branch, "w": ids["other_warehouse"]})
    db.execute(text("INSERT INTO platform.user_branch(user_id,branch_id) VALUES (:u,:b) ON CONFLICT DO NOTHING"), {"u": ids["other"], "b": ids["branch"]})
    db.commit()
    owner = headers()
    for key, qty in [("warehouse", "10"), ("other_warehouse", "3")]:
        assert client.post('/inventory/movements', headers=owner, json=movement(warehouse_id=str(ids[key]), quantity=qty)).status_code == 201
    return client, db, ids, headers, movement


@pytest.mark.parametrize('endpoint', ['stock', 'batches', 'movements', 'cover', 'expiry-warnings'])
def test_warehouse_reads_are_scoped_to_explicit_branch_grants(assigned_stock, endpoint):
    client, _db, ids, headers, _movement = assigned_stock
    auth = headers('other')
    response = client.get('/inventory/' + endpoint, headers=auth, params={'warehouse_id': str(ids['warehouse'])})
    assert response.status_code == 200
    if endpoint in {'stock', 'movements'}:
        assert response.json()
        assert {r['warehouse_id'] for r in response.json()} == {str(ids['warehouse'])}
    foreign = client.get('/inventory/' + endpoint, headers=auth, params={'warehouse_id': str(ids['other_warehouse'])})
    assert foreign.status_code in {403, 404} or (foreign.status_code == 200 and foreign.json() == [])
    unfiltered = client.get('/inventory/' + endpoint, headers=auth)
    assert unfiltered.status_code == 200
    assert all(r['warehouse_id'] == str(ids['warehouse']) for r in unfiltered.json())


@pytest.mark.parametrize('movement_type', ['opening', 'adjustment'])
def test_warehouse_cannot_write_even_assigned_stock(assigned_stock, movement_type):
    client, db, ids, headers, movement = assigned_stock
    before = db.execute(text('SELECT warehouse_id,product_id,quantity FROM inventory.stock_balance ORDER BY warehouse_id,product_id')).all()
    count = db.scalar(text('SELECT count(*) FROM inventory.stock_movement'))
    body = movement(movement_type=movement_type, reason_id=str(ids['reason']))
    response = client.post('/inventory/movements', headers=headers('other'), json=body)
    assert response.status_code == 403
    assert db.scalar(text('SELECT count(*) FROM inventory.stock_movement')) == count
    assert db.execute(text('SELECT warehouse_id,product_id,quantity FROM inventory.stock_balance ORDER BY warehouse_id,product_id')).all() == before


def test_revoked_warehouse_grant_is_denied_on_existing_session(assigned_stock):
    client, db, ids, headers, _movement = assigned_stock
    auth = headers('other')
    assert client.get('/inventory/stock', headers=auth).status_code == 200
    db.execute(text('DELETE FROM platform.user_branch WHERE user_id=:u'), {'u': ids['other']})
    db.commit()
    response = client.get('/inventory/stock', headers=auth)
    assert response.status_code == 403
