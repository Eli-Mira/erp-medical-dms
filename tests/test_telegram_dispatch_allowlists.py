"""Every dispatch path requires both Telegram allowlists, before any reply/query."""

from unittest.mock import Mock

import httpx
import pytest
from app.telegram.bot import TelegramBot
from app.telegram.config import TelegramConfig


@pytest.fixture
def dispatch(monkeypatch):
    config = TelegramConfig(
        bot_token="",
        readonly_db_url="",
        allowed_user_ids=frozenset({123}),
        allowed_chat_ids=frozenset({123, -100123}),
    )
    bot = TelegramBot(config)
    bot._send_message = Mock()
    bot._run_template = Mock(return_value="Synthetic safe result")
    bot._log_query = Mock()
    wire = Mock(return_value=httpx.Response(200, json={"ok": True}))
    monkeypatch.setattr(httpx, "post", wire)
    return bot, wire


def update(message, user, chat, kind):
    return {
        "message": {
            "from": {"id": user},
            "chat": {"id": chat, "type": kind},
            "text": message,
        }
    }


@pytest.mark.parametrize(
    "message",
    [
        "expiry",
        "Sebaye expiry",
        "@Sebaye expiry",
        "مرحبا سيباي expiry",
        "/start",
        "/help",
    ],
)
@pytest.mark.parametrize(
    "user,chat,kind",
    [
        (999, -100123, "supergroup"),
        (123, -999, "supergroup"),
        (999, 123, "private"),
        (123, 456, "private"),
    ],
)
def test_dispatch_never_bypasses_either_allowlist(dispatch, message, user, chat, kind):
    bot, _wire = dispatch
    bot._handle_command(update(message, user, chat, kind))
    bot._send_message.assert_not_called()
    bot._run_template.assert_not_called()
    bot._log_query.assert_not_called()


@pytest.mark.parametrize(
    "message", ["expiry", "Sebaye expiry", "@Sebaye expiry", "مرحبا سيباي expiry"]
)
@pytest.mark.parametrize("chat,kind", [(123, "private"), (-100123, "supergroup")])
def test_both_allowlists_allow_safe_queries(dispatch, message, chat, kind):
    bot, wire = dispatch
    bot._handle_command(update(message, 123, chat, kind))
    bot._run_template.assert_called_once_with("expiry", {"days": 30})
    bot._send_message.assert_called_once_with(chat, "Synthetic safe result")
    wire.assert_not_called()


@pytest.mark.parametrize("kind", ["group", "supergroup"])
def test_unapproved_group_is_left_without_reply(dispatch, kind):
    bot, wire = dispatch
    bot._handle_command(update("@Sebaye expiry", 123, -999, kind))
    wire.assert_called_once()
    assert wire.call_args.args[0].endswith("/leaveChat")
    assert wire.call_args.kwargs == {"json": {"chat_id": -999}, "timeout": 10}
    bot._send_message.assert_not_called()
    bot._run_template.assert_not_called()


@pytest.mark.parametrize("chat,kind", [(123, "private"), (-100123, "supergroup")])
def test_start_still_replies_in_allowed_chats(dispatch, chat, kind):
    bot, _wire = dispatch
    bot._handle_command(update("/start", 123, chat, kind))
    bot._send_message.assert_called_once()
    bot._run_template.assert_not_called()
