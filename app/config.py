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

def _env_csv(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(part.strip() for part in raw.split(",") if part.strip())

# Comma-separated IPs/CIDRs of trusted reverse proxies (e.g. Cloudflare/nginx).
# Empty by default: forwarded headers are ignored unless direct peer is trusted.
RATE_LIMIT_TRUSTED_PROXIES: tuple[str, ...] = _env_csv("RATE_LIMIT_TRUSTED_PROXIES")