"""Feature surface regression; real HTTP/PG cases are a separate covering gate."""

import importlib


def test_approved_maintenance_surface_exists():
    router = importlib.import_module("app.master.router").router
    actual = {
        (route.path, method) for route in router.routes for method in route.methods
    }
    required = {
        ("/master/products/{product_id}", "GET"),
        ("/master/products/{product_id}/activate", "PATCH"),
        ("/master/products-maintenance", "GET"),
        ("/master/products/{product_id}", "DELETE"),
        ("/master/products", "POST"),
        ("/master/products/{product_id}", "PATCH"),
    }
    assert required <= actual, "Missing approved maintenance paths: " + repr(
        required - actual
    )
