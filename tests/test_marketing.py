"""Marketing spend + objective/KPI (V2 §2B.16-2B.18)."""

pytest_plugins = ["test_invoice_api"]


def test_spend_with_products_and_objective(invoice_env):
    client, _db, ids, _payload, headers = invoice_env
    body = client.post("/marketing/spend", headers=headers("owner"), json={
        "kol_id": None,
        "territory_id": str(ids["territory"]),
        "spend_date": "2026-10-01",
        "amount": "1500.00",
        "activity_type": "conference",
        "notes": "launch",
        "product_ids": [str(ids["product"])],
    })
    assert body.status_code == 201, body.text
    sid = body.json()["id"]
    assert body.json()["product_ids"] == [str(ids["product"])]
    listed = client.get("/marketing/spend", headers=headers("owner")).json()
    assert len(listed) == 1
    ob = client.post("/marketing/objectives", headers=headers("owner"), json={
        "spend_id": sid,
        "territory_id": str(ids["territory"]),
        "objective": "increase awareness",
        "expected_kpi": "50 visits",
        "actual_result": "40 visits",
        "followup_notes": "follow up Q4",
    })
    assert ob.status_code == 201, ob.text
    objs = client.get("/marketing/objectives", headers=headers("owner")).json()
    assert len(objs) == 1 and objs[0]["objective"] == "increase awareness"


def test_spend_missing_fields(invoice_env):
    client, _db, _ids, _payload, headers = invoice_env
    assert client.post("/marketing/spend", headers=headers("owner"), json={}).status_code == 422


def test_marketing_unauthenticated(invoice_env):
    client, _db, _ids, _payload, _headers = invoice_env
    assert client.post("/marketing/spend", json={}).status_code == 401
    assert client.get("/marketing/spend").status_code == 401
