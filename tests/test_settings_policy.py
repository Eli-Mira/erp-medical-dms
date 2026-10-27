"""GET/PUT /settings/inventory-policy: D41 defaults, owner-only writes."""

from sqlalchemy import text

pytest_plugins = ["test_inventory_api"]


def test_defaults_are_d41(stock_env):
    """Before any configuration the approved defaults are served (30 / 180)."""
    client, _db, _ids, headers, _m = stock_env
    body = client.get("/settings/inventory-policy", headers=headers("owner"))
    assert body.status_code == 200, body.text
    assert body.json() == {"stock_cover_window_days": 30,
                           "overstock_threshold_days": 180, "expiry_warning_days": 30}


def test_owner_write_updates_and_audits(stock_env):
    client, db, _ids, headers, _m = stock_env
    response = client.put("/settings/inventory-policy", headers=headers("owner"),
                          json={"stock_cover_window_days": 45,
                                "overstock_threshold_days": 200})
    assert response.status_code == 200, response.text
    assert response.json() == {"stock_cover_window_days": 45,
                               "overstock_threshold_days": 200, "expiry_warning_days": 30}
    rows = db.execute(
        text("SELECT key, value FROM platform.platform_setting WHERE key IN "
             "('stock_cover_window_days','overstock_threshold_days') "
             "ORDER BY key")).all()
    assert rows == [("overstock_threshold_days", "200"),
                    ("stock_cover_window_days", "45")]
    event = db.execute(
        text("SELECT action, entity_type, new_values::text FROM audit.audit_log "
             "WHERE entity_type='platform_setting'")).one()
    assert event[0] == "settings_changed" and "45" in event[2]


def test_non_owner_write_is_denied(stock_env):
    client, db, _ids, headers, _m = stock_env
    response = client.put("/settings/inventory-policy", headers=headers("other"),
                          json={"stock_cover_window_days": 45,
                                "overstock_threshold_days": 200})
    assert response.status_code == 403
    assert db.execute(text(
        "SELECT count(*) FROM platform.platform_setting")).scalar_one() == 0


def test_invalid_values_rejected(stock_env):
    client, _db, _ids, headers, _m = stock_env
    response = client.put("/settings/inventory-policy", headers=headers("owner"),
                          json={"stock_cover_window_days": 0,
                                "overstock_threshold_days": 200})
    assert response.status_code == 422


def test_unauthenticated_denied(stock_env):
    client, _db, _ids, _headers, _m = stock_env
    assert client.get("/settings/inventory-policy").status_code == 401
    assert client.put(
        "/settings/inventory-policy", json={}).status_code == 401
