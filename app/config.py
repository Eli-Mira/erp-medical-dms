"""Feature flags driven by environment variables."""
import os


def _env_flag(name, default):
    """Return True if the env var is a truthy literal, else default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


POSTING_ENABLED = _env_flag("POSTING_ENABLED", False)
# Presentation only: when on, the PWA may show the demo-account hint. Never
# gates or relaxes any business rule; purely cosmetic (see app.main /meta).
DEMO_MODE = _env_flag("DEMO_MODE", False)