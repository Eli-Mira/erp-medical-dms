"""Medical Company System API (Phase 2 — Platform Foundation).

Current scope: service scaffold + health probe. Auth/RBAC, audit logging,
settings, posting states and PWA shell are added progressively in Phase 2.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(title="Medical Company System", version="0.1.0")
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


@app.get("/")
def root() -> dict:
    return {"service": "Medical Company System", "docs": "/docs", "health": "/health"}
