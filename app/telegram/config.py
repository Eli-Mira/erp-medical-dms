"""Telegram bot configuration — token from environment, never hardcoded."""
import os
from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    # Allowlisted user IDs (private chat)
    allowed_user_ids: FrozenSet[int] = field(default_factory=frozenset)
    # Allowlisted chat IDs (groups)
    allowed_chat_ids: FrozenSet[int] = field(default_factory=frozenset)
    # Read-only DB role connection string
    readonly_db_url: str = field(default_factory=lambda: os.environ.get("TELEGRAM_READONLY_DB_URL", ""))
    # Polling interval in seconds
    poll_interval: int = 2

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.readonly_db_url)

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        user_ids = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
        chat_ids = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
        return cls(
            bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            allowed_user_ids=frozenset(
                int(x.strip()) for x in user_ids.split(",") if x.strip().isdigit()
            ),
            allowed_chat_ids=frozenset(
                int(x.strip()) for x in chat_ids.split(",") if x.strip().isdigit()
            ),
            readonly_db_url=os.environ.get("TELEGRAM_READONLY_DB_URL", ""),
        )
