"""Medical Company System API (Phase 2 — Platform Foundation).

Current scope: service scaffold + health probe. Auth/RBAC, audit logging,
settings, posting states and PWA shell are added progressively in Phase 2.
"""

import base64
import hashlib
import os

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders

# Request body size cap (1 MiB)
MAX_REQUEST_BODY_BYTES = 1_048_576

# Match the existing inline service-worker registration without allowing other scripts.
_SERVICE_WORKER_SCRIPT = (
    '\n    if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");\n  '
)
_SCRIPT_HASH = base64.b64encode(
    hashlib.sha256(_SERVICE_WORKER_SCRIPT.encode("utf-8")).digest()
).decode("ascii")
_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        f"script-src 'self' 'sha256-{_SCRIPT_HASH}'; "
        # Existing markup and JS use inline styles; fonts use Google's stylesheet.
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self'; connect-src 'self'; worker-src 'self'; "
        "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


class HardenedFastAPI(FastAPI):
    def build_middleware_stack(self):
        # Wrap ServerErrorMiddleware too, so unhandled 500s get the same headers.
        inner = super().build_middleware_stack()

        async def secured(scope, receive, send):
            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = MutableHeaders(scope=message)
                    for name, value in _SECURITY_HEADERS.items():
                        headers[name] = value
                await send(message)

            await inner(scope, receive, send_with_headers)

        return secured


app = HardenedFastAPI(
    title="Medical Company System", version="0.1.0", debug=False,
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.add_middleware(GZipMiddleware, minimum_size=500)

_CACHEABLE = {".js", ".css", ".svg", ".png", ".webp", ".woff2"}
_PAGES = {"", ".html"}


@app.middleware("http")
async def reject_nul_bytes(request, call_next):
    """Reject raw or percent-encoded NUL bytes in query/path/JSON bodies with 422,
    enforce request body size limits, and reject NUL bytes in headers."""
    # 1️⃣ Header NUL‑byte check
    for raw_k, raw_v in request.scope.get("headers", []):
        if b"\x00" in raw_k or b"\x00" in raw_v:
            return JSONResponse({"detail": "Null bytes are not allowed"}, status_code=422)

    # 2️⃣ Query‑string / path NUL‑byte check (unchanged)
    raw_qs = request.scope.get("query_string", b"")
    if b"\x00" in raw_qs or b"%00" in raw_qs.lower() or "\x00" in request.url.path:
        return JSONResponse({"detail": "Null bytes are not allowed"}, status_code=422)

    # 3️⃣ Content‑Length size cap
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
        except ValueError:
            pass  # ignore malformed header; further checks will catch oversized bodies

    ct = (request.headers.get("content-type") or "").lower()

    # 4️⃣ Body size & JSON NUL‑byte checks for mutable methods
    if request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        if "application/json" in ct:
            if b"\x00" in body or b"\\u0000" in body.lower():
                return JSONResponse({"detail": "Null bytes are not allowed"}, status_code=422)

    # All checks passed – forward the request.
    return await call_next(request)


@app.middleware("http")
async def static_cache_headers(request, call_next):
    """Hash-free static assets get a short public cache; the shell stays fresh."""
    response = await call_next(request)
    if request.url.path.startswith("/app/"):
        ext = os.path.splitext(request.url.path)[1].lower()
        if ext in _CACHEABLE:
            response.headers["Cache-Control"] = "public, max-age=3600"
        elif ext in _PAGES:
            response.headers["Cache-Control"] = "no-cache"
    return response


from app.auth.router import router as auth_router

app.include_router(auth_router)
from app.auth.rbac import rbac_router

app.include_router(rbac_router)
from app.sales.router import router as invoice_router

app.include_router(invoice_router)
from app.sales.target_router import router as targets_router

app.include_router(targets_router)
from app.inventory.router import router as inventory_router

app.include_router(inventory_router)
from app.finance.router import router as ar_router

app.include_router(ar_router)
from app.finance.payment_router import router as collections_router

app.include_router(collections_router)
from app.audit.router import router as audit_router
from app.marketing.router import router as marketing_router
from app.master.router import router as master_router
from app.private_accounts.router import router as private_accounts_router
from app.reason_codes.router import router as reason_codes_router
from app.returns.router import router as returns_router
from app.search.router import router as search_router
from app.transfers.router import router as transfers_router
from app.visits.router import router as visits_router

app.include_router(master_router)
app.include_router(private_accounts_router)
app.include_router(reason_codes_router)
app.include_router(search_router)
app.include_router(transfers_router)
app.include_router(visits_router)
app.include_router(returns_router)
app.include_router(marketing_router)
app.include_router(audit_router)
from app.settings.router import router as settings_router

app.include_router(settings_router)
from app.reports.router import router as reports_router

app.include_router(reports_router)

from fastapi.staticfiles import StaticFiles

from app.config import DEMO_MODE

app.mount("/app", StaticFiles(directory="web", html=True), name="pwa")


@app.get("/meta")
def meta() -> dict:
    """Presentation flags for the PWA shell.

    ``demo_mode`` only lets the login screen show the demo-account hint. It
    carries no business state and never relaxes authorization or the
    ``POSTING_ENABLED`` safety gate.
    """
    return {"demo_mode": DEMO_MODE}


import json
import logging
import time
import uuid
import re
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

@app.middleware("http")
async def request_id_and_json_log(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID")
    if not req_id or not re.fullmatch(r"[A-Za-z0-9\-_]{1,64}", req_id):
        req_id = uuid.uuid4().hex
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = req_id
    logging.getLogger("medical_dms.http").info(
        json.dumps(
            {
                "request_id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }
        )
    )
    return response

@app.get("/livez")
def livez() -> dict:
    return {"status": "alive", "service": "medical-dms"}

@app.get("/readyz")
def readyz() -> dict:
    from app import db as app_db

    try:
        with app_db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception:
        return JSONResponse({"status": "degraded", "db": "unavailable"}, status_code=503)

@app.get("/health")
def health() -> dict:
    """Readiness probe: used by Docker + CI to confirm the API boots."""
    return {"status": "ok", "service": "medical-dms", "phase": "platform-foundation"}


@app.get("/")
def root() -> dict:
    return {"service": "Medical Company System", "docs": None, "health": "/health"}
