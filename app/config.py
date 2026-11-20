"""Feature flags driven by environment variables."""
import ipaddress
import os


def _env_flag(name, default):
    """Return True if the env var is a truthy literal, else default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_trusted_proxies(raw: str | None) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Parse comma-separated IP/CIDR entries; fail closed on wildcards or malformed values."""
    if not raw or not raw.strip():
        return ()
    networks = []
    for token in raw.split(","):
        entry = token.strip()
        if not entry:
            continue
        if entry == "*":
            raise ValueError("RATE_LIMIT_TRUSTED_PROXIES must not contain wildcard '*'")
        net = ipaddress.ip_network(entry, strict=False)
        if net.prefixlen == 0:
            raise ValueError("RATE_LIMIT_TRUSTED_PROXIES must not allow 0.0.0.0/0 or ::/0")
        networks.append(net)
    return tuple(networks)


POSTING_ENABLED = _env_flag("POSTING_ENABLED", False)
# Presentation only: when on, the PWA may show the demo-account hint. Never
# gates or relaxes any business rule; purely cosmetic (see app.main /meta).
DEMO_MODE = _env_flag("DEMO_MODE", False)
RATE_LIMIT_TRUSTED_PROXIES = parse_trusted_proxies(
    os.environ.get("RATE_LIMIT_TRUSTED_PROXIES")
)
