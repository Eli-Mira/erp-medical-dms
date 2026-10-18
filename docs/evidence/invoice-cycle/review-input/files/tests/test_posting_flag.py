"""Feature-flag gate for the invoice posting endpoint.

The flag POSTING_ENABLED defaults to OFF. When OFF the endpoint keeps
returning 409 with the unchanged message; when ON it delegates to
app.sales.service.post_invoice_atomic.
"""

from uuid import UUID

from app.sales import service
from app.sales.service import post_invoice_atomic


def test_flag_defaults_off(posting_env, monkeypatch):
    """Without POSTING_ENABLED the endpoint stays 409 with the old message."""
    monkeypatch.delenv("POSTING_ENABLED", raising=False)
    monkeypatch.setattr("app.sales.router.POSTING_ENABLED", False)
    client, _db, _ids, auth, invoice, _payload = posting_env
    response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    assert response.status_code == 409
    assert "disabled" in response.json()["detail"].lower()
    # nothing was posted
    assert (
        client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"]
        == "Draft"
    )


def test_flag_on_delegates_to_atomic(posting_env, monkeypatch):
    """With the flag ON the endpoint delegates to post_invoice_atomic once."""
    monkeypatch.setenv("POSTING_ENABLED", "true")
    monkeypatch.setattr("app.sales.router.POSTING_ENABLED", True)
    client, _db, ids, auth, invoice, _payload = posting_env

    calls = []

    def fake_post_invoice_atomic(db_, invoice_id, actor_id):
        calls.append({"db": db_, "invoice_id": invoice_id, "actor_id": actor_id})
        # a complete InvoiceOut-shaped dict so the route's model_validate passes
        return {
            **invoice,
            "posting_status": "Draft",
            "id": str(invoice_id),
            "version": 1,
        }

    real = service.post_invoice_atomic
    monkeypatch.setattr(service, "post_invoice_atomic", fake_post_invoice_atomic)
    try:
        response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    finally:
        # the real atomic function must not have been the one invoked
        assert service.post_invoice_atomic is fake_post_invoice_atomic

    assert response.status_code == 200
    body = response.json()
    assert body["posting_status"] == "Draft"
    assert body["id"] == invoice["id"]
    assert body["version"] == 1
    assert len(calls) == 1
    assert calls[0]["invoice_id"] == UUID(invoice["id"])
    assert calls[0]["actor_id"] == ids["owner"]
    # the real atomic function was never called: no DB side effects
    assert (
        client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"]
        == "Draft"
    )
    assert real is post_invoice_atomic  # the original is untouched


def test_flag_on_with_depleted_stock_returns_409(posting_env, monkeypatch):
    """With the flag ON and depleted stock the endpoint returns 409, no exception."""
    from sqlalchemy import text

    monkeypatch.setenv("POSTING_ENABLED", "true")
    monkeypatch.setattr("app.sales.router.POSTING_ENABLED", True)
    client, db, ids, auth, invoice, _payload = posting_env
    # deplete stock to a single unit; the invoice line needs 2

    db.execute(
        text(
            "UPDATE inventory.stock_balance SET quantity=1 WHERE warehouse_id=:w AND product_id=:p"
        ),
        {"w": ids["warehouse"], "p": ids["product"]},
    )
    db.commit()

    response = client.post(f"/invoices/{invoice['id']}/post", headers=auth)
    assert response.status_code == 409
    assert "stock" in response.json()["detail"].lower()
    # nothing was posted; the transaction rolled back
    assert (
        client.get(f"/invoices/{invoice['id']}", headers=auth).json()["posting_status"]
        == "Draft"
    )
