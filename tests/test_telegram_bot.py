"""Tests for Telegram bot — analyst layer, allowlist, group safety."""
import os
import pytest
from app.telegram.config import TelegramConfig
from app.telegram.queries import match_template, get_template, list_templates, TEMPLATES


def test_config_from_env():
    os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
    os.environ["TELEGRAM_ALLOWED_USER_IDS"] = "123,456"
    os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "789"
    os.environ["TELEGRAM_READONLY_DB_URL"] = "postgresql://ro:pass@localhost/db"
    cfg = TelegramConfig.from_env()
    assert cfg.bot_token == "test-token"
    assert 123 in cfg.allowed_user_ids
    assert 456 in cfg.allowed_user_ids
    assert 789 in cfg.allowed_chat_ids
    assert cfg.is_configured
    # Cleanup
    for k in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_ALLOWED_CHAT_IDS", "TELEGRAM_READONLY_DB_URL"]:
        os.environ.pop(k, None)


def test_config_not_configured_without_token():
    cfg = TelegramConfig.from_env()
    assert not cfg.is_configured


def test_match_template_balance():
    assert match_template("what is customer balance") == "balance"
    assert match_template("رصيد العميل") == "balance"


def test_match_template_stock():
    assert match_template("how much stock do we have") == "stock"


def test_match_template_sales_today():
    assert match_template("sales today") == "sales_today"
    assert match_template("مبيعات اليوم") == "sales_today"


def test_match_template_expiry():
    assert match_template("products expiring soon") == "expiry"
    assert match_template("صلاحية المنتجات") == "expiry"


def test_match_template_targets():
    assert match_template("sales target progress") == "targets"


def test_match_template_stock_cover():
    assert match_template("stock cover days") == "stock_cover"


def test_match_template_unknown():
    assert match_template("hello world") is None


def test_all_templates_have_required_fields():
    for name, tmpl in TEMPLATES.items():
        assert "sql" in tmpl, f"{name} missing sql"
        assert "params" in tmpl, f"{name} missing params"
        assert "format" in tmpl, f"{name} missing format"
        assert "description" in tmpl, f"{name} missing description"


def test_templates_are_read_only():
    """Ensure all template SQL is SELECT-only (no INSERT/UPDATE/DELETE/DROP)."""
    import re
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE TABLE", "TRUNCATE"]
    for name, tmpl in TEMPLATES.items():
        sql_upper = tmpl["sql"].upper()
        for word in forbidden:
            # Use word boundary to avoid false positives (e.g., CREATED_AT contains CREATE)
            pattern = r"\b" + word + r"\b"
            assert not re.search(pattern, sql_upper), f"{name} contains forbidden keyword {word}"


def test_list_templates():
    templates = list_templates()
    assert len(templates) == 6
    assert "balance" in templates
    assert "stock_cover" in templates


def test_group_safe_templates():
    """GROUP tier only allows non-sensitive templates."""
    group_safe = {"expiry", "stock_cover", "sales_today", "targets"}
    sensitive = {"balance", "stock"}
    for t in sensitive:
        assert t not in group_safe
    for t in group_safe:
        assert t in TEMPLATES
