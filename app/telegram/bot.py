"""Telegram bot — read-only commands, httpx-based, no bot framework.

Uses Telegram Bot API via httpx. Polls for updates, dispatches commands,
runs approved query templates against read-only DB role, logs every query.
"""
import logging
import os
import time
from typing import Optional, Dict, Any

import httpx
from sqlalchemy import create_engine, text

from app.telegram.config import TelegramConfig
from app.telegram.queries import match_template, get_template

logger = logging.getLogger("telegram_bot")

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramBot:
    def __init__(self, config: TelegramConfig):
        self.config = config
        self._offset = 0
        self._running = False
        self._engine = None
        if config.readonly_db_url:
            self._engine = create_engine(config.readonly_db_url, pool_pre_ping=True)

    def _api_url(self, method: str) -> str:
        return f"{TELEGRAM_API.format(token=self.config.bot_token)}/{method}"

    def _send_message(self, chat_id: int, text: str) -> None:
        try:
            httpx.post(
                self._api_url("sendMessage"),
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def _is_allowed_user(self, user_id: int) -> bool:
        return user_id in self.config.allowed_user_ids

    def _is_allowed_chat(self, chat_id: int) -> bool:
        return chat_id in self.config.allowed_chat_ids

    def _is_group(self, chat_type: str) -> bool:
        return chat_type in ("group", "supergroup")

    def _log_query(self, user_id: int, chat_id: int, template: str, params: dict) -> None:
        logger.info(
            f"TG_QUERY user={user_id} chat={chat_id} template={template} params={params}"
        )

    def _run_template(self, template_name: str, params: dict, user_role: str = "viewer") -> str:
        tmpl = get_template(template_name)
        if not tmpl:
            return "Unknown query template."

        # GROUP tier: only non-sensitive templates
        group_safe = {"expiry", "stock_cover", "sales_today", "targets"}
        # PRIVATE tier: all templates including sensitive ones
        # (role scoping handled by DB role)

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(tmpl["sql"]), params)
                rows = result.fetchall()
            return tmpl["format"](rows)
        except Exception as e:
            logger.error(f"Query error: {e}")
            return "Query failed. Please try again."

    def _handle_command(self, update: dict) -> None:
        message = update.get("message", {})
        chat = message.get("chat", {})
        user = message.get("from", {})
        chat_id = chat.get("id")
        user_id = user.get("id")
        chat_type = chat.get("type", "private")
        text_input = message.get("text", "")

        if not chat_id or not user_id:
            return

        is_group = self._is_group(chat_type)

        if not self._is_allowed_chat(chat_id):
            if is_group:
                try:
                    httpx.post(
                        self._api_url("leaveChat"),
                        json={"chat_id": chat_id},
                        timeout=10,
                    )
                except Exception:
                    pass
            return
        if not self._is_allowed_user(user_id):
            return

        # Commands
        if text_input.startswith("/start"):
            self._send_message(chat_id, "ElsebaeyPharma ERP Bot. Send a question or use /help.")
            return

        if text_input.startswith("/help"):
            templates = list(get_template.__wrapped__ if hasattr(get_template, "__wrapped__") else None) or []
            from app.telegram.queries import list_templates
            self._send_message(
                chat_id,
                "Available queries:\n" + "\n".join(f"- {t}" for t in list_templates()),
            )
            return

        # Natural language analyst layer
        template_name = match_template(text_input)
        if template_name:
            # GROUP tier: block sensitive queries
            sensitive = {"balance", "stock"}  # balance=finance, stock=sensitive inventory
            # Actually: GROUP = non-sensitive alerts/summaries only
            group_safe = {"expiry", "stock_cover", "sales_today", "targets"}
            if is_group and template_name not in group_safe:
                self._send_message(
                    chat_id,
                    "This query is only available in private chat.",
                )
                return

            # Extract params from question (simple keyword extraction)
            params = self._extract_params(text_input, template_name)
            self._log_query(user_id, chat_id, template_name, params)
            answer = self._run_template(template_name, params)
            self._send_message(chat_id, answer)
            return

        # No match
        self._send_message(
            chat_id,
            "I didn't understand. Try: balance, stock, sales today, expiry, targets, stock cover.",
        )

    def _extract_params(self, question: str, template_name: str) -> dict:
        """Extract parameters from question text. Simple, deterministic."""
        params = {}
        tmpl = get_template(template_name)
        if not tmpl:
            return params
        for p in tmpl["params"]:
            # Look for numbers in the question
            import re
            numbers = re.findall(r"\d+", question)
            if p in ("customer_id", "product_id", "target_id"):
                if numbers:
                    params[p] = int(numbers[0])
            elif p == "days":
                if numbers:
                    params[p] = int(numbers[0])
                else:
                    params[p] = 30  # default 30 days
        return params

    def poll(self) -> None:
        """Poll for updates. Runs until stopped."""
        self._running = True
        logger.info("Telegram bot started polling")
        while self._running:
            try:
                resp = httpx.get(
                    self._api_url("getUpdates"),
                    params={"offset": self._offset, "timeout": 30},
                    timeout=35,
                )
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        self._handle_command(update)
            except Exception as e:
                logger.error(f"Poll error: {e}")
                time.sleep(5)

    def stop(self) -> None:
        self._running = False
        logger.info("Telegram bot stopped")


def create_bot() -> Optional[TelegramBot]:
    config = TelegramConfig.from_env()
    if not config.is_configured:
        logger.warning("Telegram bot not configured (missing token or DB URL)")
        return None
    return TelegramBot(config)
