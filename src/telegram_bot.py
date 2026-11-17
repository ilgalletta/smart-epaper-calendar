"""Telegram bot for updating the grocery list in data/state.json.

Supports both one-shot polling during a Pi wake cycle (`--once`) and
continuous long-polling when plugged in (`--daemon`).
"""

from __future__ import annotations

import argparse
import logging
import signal
import time
from typing import Any

import requests

from src.config import StateManager, load_config

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"


class GroceryTelegramBot:
    """Lightweight synchronous Telegram Bot API client for grocery list management."""

    def __init__(
        self,
        bot_token: str | None = None,
        allowed_chat_ids: list[int | str] | None = None,
        state_manager: StateManager | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        cfg = config if config is not None else load_config()
        tg_cfg = cfg.get("telegram", {}) if isinstance(cfg.get("telegram"), dict) else {}

        self.bot_token = (
            bot_token if bot_token is not None else str(tg_cfg.get("bot_token", "") or "")
        ).strip()
        raw_ids = (
            allowed_chat_ids
            if allowed_chat_ids is not None
            else tg_cfg.get("allowed_chat_ids", [])
        )
        self.allowed_chat_ids: set[int] = set()
        if isinstance(raw_ids, list):
            for cid in raw_ids:
                try:
                    self.allowed_chat_ids.add(int(cid))
                except (TypeError, ValueError):
                    continue

        self.poll_timeout = int(tg_cfg.get("poll_timeout", 30) or 30)
        self.sm = state_manager if state_manager is not None else StateManager()
        self._running = False

    def _api_url(self, method: str) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self.bot_token}/{method}"

    def send_message(self, chat_id: int, text: str) -> bool:
        if not self.bot_token:
            return False
        try:
            resp = requests.post(
                self._api_url("sendMessage"),
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("Failed to send Telegram message to %s: %s", chat_id, exc)
            return False

    def _format_list(self) -> str:
        items = self.sm.get_grocery_list()
        if not items:
            return "Grocery list is empty."
        lines = ["Grocery List:"]
        for idx, item in enumerate(items, start=1):
            mark = "[x]" if item.get("done") else "[ ]"
            lines.append(f"{idx}. {mark} {item.get('text', '')}")
        return "\n".join(lines)

    def handle_command(self, text: str) -> str:
        """Execute a grocery command and return the reply text."""
        stripped = text.strip()
        if not stripped:
            return ""

        parts = stripped.split(maxsplit=1)
        cmd = parts[0].split("@")[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/start", "/help"):
            return (
                "Grocery Bot commands:\n"
                "/add <item> - Add an item\n"
                "/done <number or name> - Mark an item done\n"
                "/list - Show grocery list\n"
                "/clear - Remove done items (/clear all to clear everything)"
            )

        if cmd == "/add":
            if not arg:
                return "Usage: /add <item>"
            item = self.sm.add_grocery_item(arg)
            return f"Added: {item['text']}"

        if cmd == "/done":
            if not arg:
                return "Usage: /done <number or item name>"
            item = self.sm.mark_grocery_done(arg)
            if item is None:
                return f"Could not find item matching: {arg}"
            return f"Marked done: {item['text']}"

        if cmd == "/list":
            return self._format_list()

        if cmd == "/clear":
            if arg.lower() == "all":
                removed = self.sm.clear_grocery_list(completed_only=False)
                return f"Cleared all {removed} item(s)."
            removed = self.sm.clear_grocery_list(completed_only=True)
            return f"Cleared {removed} completed item(s)."

        return "Unknown command. Send /help for available commands."

    def _is_authorized(self, chat_id: int) -> bool:
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids

    def process_update(self, update: dict[str, Any]) -> str | None:
        """Process a single Telegram update dict and return the reply sent, if any."""
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return None
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = message.get("text")
        if chat_id is None or not isinstance(text, str):
            return None

        cid = int(chat_id)
        if not self._is_authorized(cid):
            logger.warning("Ignoring unauthorized Telegram chat_id=%s", cid)
            return None

        if not text.strip().startswith("/"):
            return None

        reply = self.handle_command(text)
        if reply:
            self.send_message(cid, reply)
        return reply

    def poll_once(self, timeout: int = 0) -> int:
        """Fetch and process pending updates once. Returns count of processed updates."""
        if not self.bot_token:
            logger.warning("Telegram bot_token is not configured; skipping poll.")
            return 0

        last_id = self.sm.get_telegram_offset()
        params: dict[str, Any] = {"timeout": timeout, "limit": 100}
        if last_id > 0:
            params["offset"] = last_id + 1

        try:
            resp = requests.get(
                self._api_url("getUpdates"),
                params=params,
                timeout=max(10, timeout + 10),
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.warning("Telegram getUpdates failed: %s", exc)
            return 0

        if not payload.get("ok"):
            logger.warning("Telegram API returned not ok: %s", payload)
            return 0

        updates = payload.get("result", [])
        if not isinstance(updates, list) or not updates:
            return 0

        processed = 0
        max_update_id = last_id
        for update in updates:
            uid = int(update.get("update_id", 0))
            if uid > max_update_id:
                max_update_id = uid
            if self.process_update(update) is not None:
                processed += 1

        if max_update_id > last_id:
            self.sm.set_telegram_offset(max_update_id)
            # Acknowledge offset so Telegram won't redeliver on next Pi wake cycle
            try:
                requests.get(
                    self._api_url("getUpdates"),
                    params={"offset": max_update_id + 1, "timeout": 0, "limit": 1},
                    timeout=5,
                )
            except Exception:
                pass

        return processed

    def stop(self) -> None:
        self._running = False

    def run_forever(self) -> None:
        """Continuously long-poll Telegram updates until stopped."""
        if not self.bot_token:
            raise RuntimeError("Telegram bot_token is not configured.")

        self._running = True

        def _handle_sig(_signum: int, _frame: Any) -> None:
            logger.info("Stopping Telegram bot...")
            self._running = False

        signal.signal(signal.SIGINT, _handle_sig)
        signal.signal(signal.SIGTERM, _handle_sig)

        logger.info("Starting continuous Telegram polling...")
        while self._running:
            self.poll_once(timeout=self.poll_timeout)
            if self._running:
                time.sleep(0.5)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="Smart E-Paper Calendar Telegram Grocery Bot")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Run a single getUpdates poll cycle (for Pi wake cycle) and exit.",
    )
    mode.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuous long-polling (when plugged in).",
    )
    args = parser.parse_args()

    bot = GroceryTelegramBot()
    if args.daemon:
        bot.run_forever()
    else:
        count = bot.poll_once(timeout=0)
        logger.info("Processed %d Telegram command(s).", count)


if __name__ == "__main__":
    main()
