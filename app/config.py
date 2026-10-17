"""Feature flags driven by environment variables."""
import os


def _env_flag(name, default):
    """Return True if the env var is a truthy literal, else default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


POSTING_ENABLED = _env_flag("POSTING_ENABLED", False)