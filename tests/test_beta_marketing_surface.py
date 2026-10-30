"""Feature surface regression; real HTTP/PG cases are a separate covering gate."""

import importlib


def test_approved_maintenance_surface_exists():
    router = importlib.import_module("app.marketing.router").router
    actual = {
        (route.path, method) for route in router.routes for method in route.methods
    }
    required = {
        ("/marketing/objectives/{record_id}", "GET"),
        ("/marketing/spend/{record_id}", "GET"),
        ("/marketing/objectives/{record_id}", "PATCH"),
        ("/marketing/spend/{record_id}", "PATCH"),
    }
    assert required <= actual, "Missing approved maintenance paths: " + repr(
        required - actual
    )
