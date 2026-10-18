"""GET /audit: owner/finance/auditor read-only access, paginated + filtered."""


from sqlalchemy import text

pytest_plugins = ["test_invoice_api"]


def test_audit_filters_and_pagination(invoice_env):
    client, db, ids, _payload, headers = invoice_env
    # Seed one audit row via a posting-free action: settings write.
    db.execute(text("INSERT INTO audit.audit_log (id, actor_user_id, action, "
                    "entity_type, created_at) VALUES (gen_random_uuid(), :a, "
                    "'created', 'stock_movement', now() - interval '1 second')"),
               {"a": ids["owner"]})
    db.execute(text("INSERT INTO audit.audit_log (id, actor_user_id, action, "
                    "entity_type, created_at) VALUES (gen_random_uuid(), :a, "
                    "'upserted', 'sales_target', now())"),
               {"a": ids["other"]})
    db.commit()
    body = client.get("/audit", headers=headers("owner")).json()
    assert len(body) == 2
    assert body[0]["action"] == "upserted"  # newest first

    filtered = client.get("/audit?entity_type=stock_movement", headers=headers("owner")).json()
    assert len(filtered) == 1 and filtered[0]["entity_type"] == "stock_movement"

    by_actor = client.get(f"/audit?actor_id={ids['other']}", headers=headers("owner")).json()
    assert len(by_actor) == 1

    page = client.get("/audit?limit=1&offset=1", headers=headers("owner")).json()
    assert len(page) == 1


def test_audit_access(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.get("/audit").status_code == 401
    assert client.get("/audit", headers=headers("other")).status_code == 403  # medical_rep
    assert client.get("/audit", headers=headers("owner")).status_code == 200
