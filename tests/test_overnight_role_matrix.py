"""Runtime Cartesian observations, not a claim that invalid probes prove access."""

import json
import re
from collections import Counter

from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.routing import Mount
from test_invoice_api import invoice_env as invoice_env  # noqa: PLC0414
from test_lane1_r22_territory_http import (
    require_owned_verifier_database as require_owned_verifier_database,  # noqa: PLC0414
)

from app.auth.rbac import ROLES
from app.main import app

SENTINEL = "00000000-0000-4000-8000-000000000001"
PUBLIC = {
    "/",
    "/health",
    "/meta",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/app",
}
BUSINESS = (
    "/invoices",
    "/inventory",
    "/ar",
    "/collections",
    "/marketing",
    "/master",
    "/returns",
    "/transfers",
    "/visits",
    "/reports",
    "/search",
)


def spec_expectation(role, method, path):
    """Conservative independent PRD §2 boundaries, never copied guard constants."""
    if path in PUBLIC:
        return "PUBLIC", "Public health/UI/API discovery; no business records"
    if role == "anonymous":
        return "AUTH_REQUIRED", "PRD A-01/A-02; explicit credentials required"
    if path.startswith(("/owner/", "/private-accounts")):
        return (
            "ALLOW_OWNER_ONLY" if role == "owner" else "DENY"
        ), "PRD §2 owner/private boundary; D10"
    if path.startswith("/auth/"):
        return (
            "NEEDS_EVIDENCE",
            "Session/owner-only administration needs route-specific Beta decision",
        )
    if role == "false_owner":
        return (
            "DENY",
            "Owner label without server-owned is_owner cannot grant ownership",
        )
    if role == "admin" and path.startswith(BUSINESS):
        return "DENY", "PRD §2 System Administrator: platform only"
    if role == "warehouse_staff" and path.startswith(
        ("/ar", "/collections", "/reports")
    ):
        return "DENY", "PRD §2 Warehouse: never customer debt/balance"
    if role == "read_only_auditor" and method not in {"GET", "HEAD", "OPTIONS"}:
        return "DENY", "PRD §2 Read-Only/Auditor: no create/edit/delete"
    if role == "owner":
        return (
            "ALLOW_IN_SCOPE",
            "PRD §2 Owner: all modules, with posting OFF and state validation intact",
        )
    return (
        "NEEDS_EVIDENCE",
        "PRD candidate roles do not settle every Beta endpoint/action/grant",
    )


def runtime_routes():
    """Expand the installed FastAPI included-router contexts, retaining prefixes."""
    for entry in app.routes:
        if hasattr(entry, "effective_route_contexts"):
            for context in entry.effective_route_contexts():
                yield context.original_route, context.path_format
        else:
            yield entry, entry.path


def test_every_runtime_role_and_endpoint_has_a_retained_observation(
    invoice_env, record_property
):
    client, db, ids, _payload, headers = invoice_env
    discovery = client.get("/openapi.json")
    assert discovery.status_code == 404
    schema = app.openapi()
    endpoints = []
    routes = list(runtime_routes())
    for route, path in routes:
        if isinstance(route, Mount):
            assert path == "/app", "Review any new mount before probing"
            endpoints.append(("GET", path, path + "/", None))
            continue
        for method in sorted(route.methods or set()):
            concrete = re.sub(r"\{[^}]+\}", SENTINEL, path)
            operation = schema.get("paths", {}).get(path, {}).get(method.lower())
            endpoints.append((method, path, concrete, operation))
    keys = {(method, path) for method, path, _url, _operation in endpoints}
    assert len(keys) == len(endpoints)
    registered_api = {
        (method, path)
        for route, path in routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    openapi_api = {
        (method.upper(), path)
        for path, methods in schema["paths"].items()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    }
    assert registered_api == openapi_api
    scenarios = list(ROLES) + ["false_owner", "anonymous"]
    assert len(scenarios) == len(set(scenarios))
    rows = []
    for role in scenarios:
        if role not in {"owner", "anonymous"}:
            db.execute(
                text(
                    "UPDATE platform.platform_user SET role=:r,is_owner=false WHERE id=:u"
                ),
                {"r": "owner" if role == "false_owner" else role, "u": ids["other"]},
            )
            db.commit()
        for method, path, url, operation in endpoints:
            auth = (
                {}
                if role == "anonymous"
                else headers("owner" if role == "owner" else "other")
            )
            params = {"q": "Test"} if path == "/search" else {}
            kwargs = {"headers": auth, "params": params, "follow_redirects": False}
            if method in {"POST", "PUT", "PATCH"}:
                kwargs["json"] = {}
            # Refuse to serialize bodies/tokens/actor IDs; only statuses are evidence.
            try:
                response = client.request(method, url, **kwargs)
                status = response.status_code
            except (
                SQLAlchemyError,
                RuntimeError,
                ValueError,
                TypeError,
                LookupError,
                AssertionError,
            ) as error:
                # Preserve availability failures without leaking parameter-bearing errors.
                status = None
                error_class = type(error).__name__
                db.rollback()
            else:
                error_class = None
                db.rollback()
            expected, source = spec_expectation(role, method, path)
            if status is not None and 200 <= status < 300:
                observed = "ALLOWED_THIS_PROBE"
            elif status == 403:
                observed = "DENIED"
            elif status == 401:
                observed = "AUTHENTICATION_REQUIRED_OR_REJECTED"
            elif status == 409:
                observed = "STATE_OR_POSTING_SAFETY_GATE_NOT_ROLE_PROOF"
            else:
                observed = "NOT_PROVEN"
            match = "NEEDS_EVIDENCE"
            if (
                (expected == "PUBLIC" and observed == "ALLOWED_THIS_PROBE")
                or (expected == "AUTH_REQUIRED" and status in {401, 403})
                or (expected == "DENY" and status == 403)
            ):
                match = "MATCH"
            elif (
                expected in {"ALLOW_IN_SCOPE", "ALLOW_OWNER_ONLY"}
                and observed == "ALLOWED_THIS_PROBE"
            ):
                match = "MATCH_THIS_PROBE_ONLY"
            elif expected == "DENY" and observed == "ALLOWED_THIS_PROBE":
                match = "DISCREPANCY"
            rows.append(
                {
                    "role": role,
                    "method": method,
                    "endpoint": path,
                    "expected_from_spec": expected,
                    "spec_basis": source,
                    "http_status": status,
                    "observation": observed,
                    "disposition": match,
                    "request_uses_valid_business_payload": method in {"GET", "HEAD"}
                    and "{" not in path,
                    "exception_class": error_class,
                }
            )
    assert {(row["role"], row["method"], row["endpoint"]) for row in rows} == {
        (role, method, path) for role in scenarios for method, path in keys
    }
    assert len(rows) == len(scenarios) * len(endpoints)
    record = {
        "kind": "ACTUAL_ASGI_HTTP_ROLE_ENDPOINT_OBSERVATIONS_NOT_FULL_PERMISSION_ACCEPTANCE",
        "all_actual_roles": list(ROLES),
        "extra_scenarios": ["false_owner", "anonymous"],
        "endpoint_method_count": len(endpoints),
        "pair_count": len(rows),
        "counts": dict(Counter(row["disposition"] for row in rows)),
        "server_exception_count": sum(
            row["exception_class"] is not None for row in rows
        ),
        "limitations": [
            "ASGI TestClient/real PostgreSQL, not public-network or company runtime",
            "404/422/409 and invalid payloads are NOT accepted as permission successes",
            "PRD role matrix is candidate; unresolved per-endpoint policy stays NEEDS-EVIDENCE",
            "Only actual8roles are probed; separate private-account-holder role is not declared",
            "Positive business mutations need separate complete valid payload/state/scope fixtures",
            "No credentials, tokens, usernames or concrete actor/entity IDs retained",
        ],
        "rows": rows,
    }
    record_property(
        "role_endpoint_matrix_json",
        json.dumps(record, ensure_ascii=True, separators=(",", ":")),
    )
    assert record["server_exception_count"] == 0, (
        "Runtime matrix retained availability exceptions; inspect exact case record"
    )
