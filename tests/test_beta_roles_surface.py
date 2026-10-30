"""Feature surface regression; real HTTP/PG cases are a separate covering gate."""

import importlib


def test_approved_maintenance_surface_exists():
    router = importlib.import_module("app.auth.router").router
    actual = {
        (route.path, method) for route in router.routes for method in route.methods
    }
    required = {
        ("/auth/users/{user_id}", "PUT"),
        ("/auth/users/options", "GET"),
        ("/auth/users", "GET"),
    }
    assert required <= actual, "Missing approved maintenance paths: " + repr(
        required - actual
    )
