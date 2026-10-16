"""Medical Company System API (Phase 2 — Platform Foundation).

Current scope: service scaffold + health probe. Auth/RBAC, audit logging,
settings, posting states and PWA shell are added progressively in Phase 2.
"""
from fastapi import FastAPI

app = FastAPI(title="Medical Company System", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Readiness probe: used by Docker + CI to confirm the API boots."""
    return {"status": "ok", "service": "medical-dms", "phase": "platform-foundation"}


@app.get("/")
def root() -> dict:
    return {"service": "Medical Company System", "docs": "/docs", "health": "/health"}
