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

# Phase 0 Takeover Decisions (Eli, 2026-11-21, source=eli-typed) — safe defaults behind config flags:
# T6: VAT basis (RC2-12b & sales.calc assume VAT-inclusive; accountant confirmation recorded as pending).
VAT_INCLUSIVE: bool = _env_flag("VAT_INCLUSIVE", True)
CURRENCY_CODE: str = os.environ.get("CURRENCY_CODE", "EGP").strip() or "EGP"
FISCAL_YEAR_START_MONTH: int = int(os.environ.get("FISCAL_YEAR_START_MONTH", "1"))
# T4: Invoice discount & credit-limit policy flags (soft warning by default; hard block toggleable).
REP_MAX_DISCOUNT_PCT: int = int(os.environ.get("REP_MAX_DISCOUNT_PCT", "30"))
CREDIT_LIMIT_ENFORCE: bool = _env_flag("CREDIT_LIMIT_ENFORCE", False)
DEFAULT_PAYMENT_TERMS_DAYS: int = int(os.environ.get("DEFAULT_PAYMENT_TERMS_DAYS", "30"))
# T5: Near-expiry warning/critical thresholds (days; expired batches hard-blocked on invoices).
NEAR_EXPIRY_WARN_DAYS: int = int(os.environ.get("NEAR_EXPIRY_WARN_DAYS", "90"))
NEAR_EXPIRY_CRIT_DAYS: int = int(os.environ.get("NEAR_EXPIRY_CRIT_DAYS", "30"))
# T2/A6: Telegram alerts & group mode (OFF by default until private live smoke passes).
TELEGRAM_ALERTS_ENABLED: bool = _env_flag("TELEGRAM_ALERTS_ENABLED", False)
TELEGRAM_GROUP_MODE_ENABLED: bool = _env_flag("TELEGRAM_GROUP_MODE_ENABLED", False)
# T8: Password & session policy defaults (applied by auth helpers & ops docs).
PASSWORD_MIN_LENGTH: int = int(os.environ.get("PASSWORD_MIN_LENGTH", "10"))
SESSION_IDLE_HOURS: int = int(os.environ.get("SESSION_IDLE_HOURS", "12"))
SESSION_ABSOLUTE_HOURS: int = int(os.environ.get("SESSION_ABSOLUTE_HOURS", "24"))
# T9: Offsite backup destination (rclone remote or external drive path, empty = local-only).
BACKUP_OFFSITE_TARGET: str = os.environ.get("BACKUP_OFFSITE_TARGET", "").strip()
# T10: Default branding (editable in platform_setting).
DEFAULT_COMPANY_NAME_EN: str = os.environ.get("DEFAULT_COMPANY_NAME_EN", "ElsebaeyPharma").strip()
DEFAULT_COMPANY_NAME_AR: str = os.environ.get("DEFAULT_COMPANY_NAME_AR", "شركة السباعي فارما").strip()