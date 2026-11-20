"""Medical Company System API (Phase 2 — Platform Foundation).

Current scope: service scaffold + health probe. Auth/RBAC, audit logging,
settings, posting states and PWA shell are added progressively in Phase 2.
"""

import base64
import hashlib
import os

from fastapi import FastAPI, Response, status
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text
from starlette.datastructures import MutableHeaders

from app.db import engine
from app.observability import configure_logging, wrap_request_id_middleware

http_logger = configure_logging()

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

            if scope["type"] == "http":
                qs = scope.get("query_string") or b""
                path = scope.get("path") or ""
                if b"\x00" in qs or b"%00" in qs.lower() or "\x00" in path:
                    body = b'{"detail":"Request parameters cannot contain null characters"}'
                    await send_with_headers(
                        {
                            "type": "http.response.start",
                            "status": 422,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode("ascii")),
                            ],
                        }
                    )
                    await send_with_headers(
                        {"type": "http.response.body", "body": body}
                    )
                    return

            await inner(scope, receive, send_with_headers)

        return wrap_request_id_middleware(secured, logger=http_logger)


app = HardenedFastAPI(
    title="Medical Company System", version="0.1.0", debug=False,
    docs_url=None, redoc_url=None, openapi_url=None,
)
app.add_middleware(GZipMiddleware, minimum_size=500)

_CACHEABLE = {".js", ".css", ".svg", ".png", ".webp", ".woff2"}
_PAGES = {"", ".html"}


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


@app.get("/health")
def health() -> dict:
    """Readiness probe: used by Docker + CI to confirm the API boots."""
    return {"status": "ok", "service": "medical-dms", "phase": "platform-foundation"}


@app.get("/livez")
def livez() -> dict[str, str]:
    """Liveness probe: process and event loop alive without touching PostgreSQL."""
    return {"status": "alive"}


@app.get("/readyz")
def readyz(response: Response) -> dict[str, str]:
    """Readiness probe: bounded DB connectivity + Alembic head check."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SET LOCAL statement_timeout = 2000"))
            conn.execute(text("SELECT 1"))
            ver = conn.execute(
                text("SELECT version_num FROM public.alembic_version LIMIT 1")
            ).scalar_one_or_none()
            conn.commit()
            if not ver:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                return {"status": "not_ready", "db": "unmigrated"}
        return {"status": "ready", "db": "ok"}
    except Exception as exc:
        http_logger.warning(
            "readiness_check_failed", extra={"error_type": type(exc).__name__}
        )
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "db": "unavailable"}


@app.get("/")
def root() -> dict:
    return {"service": "Medical Company System", "docs": None, "health": "/health"}
