"""Medical Company System API (Phase 2 — Platform Foundation).

Current scope: service scaffold + health probe. Auth/RBAC, audit logging,
settings, posting states and PWA shell are added progressively in Phase 2.
"""

from fastapi import FastAPI

app = FastAPI(title="Medical Company System", version="0.1.0")

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
from app.master.router import router as master_router

app.include_router(master_router)
from app.settings.router import router as settings_router

app.include_router(settings_router)

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
