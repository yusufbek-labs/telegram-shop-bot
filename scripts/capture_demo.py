"""Play a purchase scenario through the real handlers and record every Bot API call the user would see.

Usage: python -m scripts.capture_demo      (writes docs/demo/transcript.json)
Telegram is replaced by a recording session, as in tests/conftest.py; nothing is typed in by hand:
all bot text and buttons come from the actual handlers, and button taps use the callback data of the
buttons the bot really sent.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
    SendPhoto,
)
from aiogram.types import Chat, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.bot import build_dispatcher
from app.config import Settings
from app.db.session import create_engine_and_sessionmaker, init_db
from scripts.seed import seed

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo" / "transcript.json"

ADMIN_ID = 1000
CUSTOMER_ID = 2000
CUSTOMER_NAME = "Alex Morgan"
CUSTOMER_PHONE = "+1 555 0100"
CUSTOMER_ADDRESS = "42 Birch Lane, Springfield"
START = datetime.now(timezone.utc).replace(microsecond=0)


class Recorder(BaseSession):
    """Records every user-visible Bot API call instead of sending it."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict] = []
        self.actor = CUSTOMER_ID
        self.clock = 0
        self.markups: dict[tuple[int, int], InlineKeyboardMarkup] = {}
        self.texts: dict[tuple[int, int], str] = {}
        self.order: list[tuple[int, int]] = []
        self._ids = itertools.count(100)

    async def close(self) -> None:
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover - unused
        yield b""

    def tick(self, seconds: int) -> str:
        self.clock += seconds
        return (START + timedelta(seconds=self.clock)).strftime("%H:%M:%S")

    @staticmethod
    def _inline(markup) -> list[list[str]] | None:
        if isinstance(markup, InlineKeyboardMarkup):
            return [[b.text for b in row] for row in markup.inline_keyboard]
        return None

    @staticmethod
    def _reply(markup) -> list[list[str]] | None:
        if isinstance(markup, ReplyKeyboardMarkup):
            return [[b.text for b in row] for row in markup.keyboard]
        return None

    def _remember(self, chat_id: int, message_id: int, text: str, markup) -> None:
        key = (chat_id, message_id)
        if isinstance(markup, InlineKeyboardMarkup):
            self.markups[key] = markup
        self.texts[key] = text
        if key in self.order:
            self.order.remove(key)
        self.order.append(key)

    async def make_request(self, bot: Bot, method, timeout=None):
        ts = self.tick(1)
        if isinstance(method, (SendMessage, SendPhoto)):
            chat_id = method.chat_id
            message_id = next(self._ids)
            is_photo = isinstance(method, SendPhoto)
            text = method.caption if is_photo else method.text
            event = {
                "type": "photo" if is_photo else "send", "ts": ts, "chat": chat_id, "message_id": message_id,
                "text": text, "parse_mode": "HTML",
                "keyboard": self._inline(method.reply_markup), "reply_keyboard": self._reply(method.reply_markup),
                "reply_keyboard_removed": isinstance(method.reply_markup, ReplyKeyboardRemove),
            }
            if is_photo:
                event["photo"] = method.photo if isinstance(method.photo, str) else "upload"
            self.events.append(event)
            self._remember(chat_id, message_id, text, method.reply_markup)
            return Message(message_id=message_id, date=datetime.now(), chat=Chat(id=chat_id, type="private"), text=text)
        if isinstance(method, EditMessageText):
            chat_id = method.chat_id if method.chat_id is not None else self.actor
            self.events.append({
                "type": "edit", "ts": ts, "chat": chat_id, "message_id": method.message_id,
                "text": method.text, "parse_mode": "HTML", "keyboard": self._inline(method.reply_markup),
            })
            self._remember(chat_id, method.message_id, method.text, method.reply_markup)
            return Message(message_id=method.message_id, date=datetime.now(),
                           chat=Chat(id=chat_id, type="private"), text=method.text)
        if isinstance(method, EditMessageReplyMarkup):
            chat_id = method.chat_id if method.chat_id is not None else self.actor
            self.events.append({
                "type": "edit_markup", "ts": ts, "chat": chat_id, "message_id": method.message_id,
                "keyboard": self._inline(method.reply_markup),
            })
            if isinstance(method.reply_markup, InlineKeyboardMarkup):
                self.markups[(chat_id, method.message_id)] = method.reply_markup
            return True
        if isinstance(method, AnswerCallbackQuery) and method.text:
            self.events.append({
                "type": "alert" if method.show_alert else "toast", "ts": ts, "chat": self.actor, "text": method.text,
            })
        return True


class Scenario:
    def __init__(self, settings: Settings, sessionmaker) -> None:
        self.session = Recorder()
        self.bot = Bot(token=settings.bot_token, session=self.session,
                       default=DefaultBotProperties(parse_mode="HTML"))
        self.dp = build_dispatcher(settings, sessionmaker)
        self._update_ids = itertools.count(1)

    @staticmethod
    def _user(uid: int, name: str) -> dict:
        return {"id": uid, "is_bot": False, "first_name": name, "language_code": "en"}

    def _message(self, uid: int, name: str, text: str | None, message_id: int | None = None) -> dict:
        return {"message_id": message_id or next(self._update_ids), "date": 1_700_000_000,
                "chat": {"id": uid, "type": "private"}, "from": self._user(uid, name), "text": text}

    async def say(self, uid: int, name: str, text: str) -> None:
        self.session.actor = uid
        self.session.events.append({"type": "user_text", "ts": self.session.tick(12), "chat": uid, "text": text})
        update = {"update_id": next(self._update_ids), "message": self._message(uid, name, text)}
        await self.dp.feed_raw_update(self.bot, update)

    def snap(self, uid: int, name: str, last: int) -> None:
        """Mark a moment worth a screenshot: the chat as it looks now, showing its last `last` messages."""
        self.session.events.append({
            "type": "snapshot", "ts": self.session.tick(2), "chat": uid, "name": name, "last": last,
        })

    def _find_button(self, uid: int, label: str, near: str | None):
        for key in reversed(self.session.order):
            if key[0] != uid or key not in self.session.markups:
                continue
            if near is not None and near not in self.session.texts[key]:
                continue
            for row in self.session.markups[key].inline_keyboard:
                for button in row:
                    if label in button.text and button.callback_data:
                        return key, button
        raise LookupError(f"no button {label!r} (near {near!r}) in chat {uid}")

    async def tap(self, uid: int, name: str, label: str, near: str | None = None) -> None:
        (_, message_id), button = self._find_button(uid, label, near)
        self.session.actor = uid
        self.session.events.append({
            "type": "user_tap", "ts": self.session.tick(9), "chat": uid, "label": button.text, "message_id": message_id,
        })
        update = {
            "update_id": next(self._update_ids),
            "callback_query": {
                "id": str(next(self._update_ids)), "from": self._user(uid, name), "chat_instance": "ci",
                "data": button.callback_data,
                "message": self._message(uid, name, self.session.texts[(uid, message_id)], message_id),
            },
        }
        await self.dp.feed_raw_update(self.bot, update)


async def run_scenario() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            _env_file=None, bot_token="42:" + "A" * 35, admin_ids=[ADMIN_ID],
            db_path=str(Path(tmp) / "demo.db"),
        )
        engine, sessionmaker = create_engine_and_sessionmaker(settings.db_url)
        await init_db(engine)
        await seed(sessionmaker)
        s = Scenario(settings, sessionmaker)
        c, a = (CUSTOMER_ID, CUSTOMER_NAME), (ADMIN_ID, "Sam Admin")

        await s.say(*c, "/start")
        await s.say(*c, "/catalog")
        s.snap(c[0], "menu-catalog", last=4)
        await s.tap(*c, "Tea")
        await s.tap(*c, "Add to cart", near="Alpine Green Tea")
        await s.tap(*c, "Add to cart", near="Alpine Green Tea")
        await s.tap(*c, "Back")
        await s.tap(*c, "Candles")
        s.snap(c[0], "product-cards", last=5)
        await s.tap(*c, "Add to cart", near="Pine Forest Candle")
        await s.tap(*c, "Cart")
        s.snap(c[0], "cart", last=1)
        await s.tap(*c, "Checkout")
        await s.say(*c, CUSTOMER_NAME)
        s.snap(c[0], "checkout", last=3)
        await s.say(*c, CUSTOMER_PHONE)
        await s.say(*c, CUSTOMER_ADDRESS)
        await s.tap(*c, "Cash on delivery")
        s.snap(c[0], "order-summary", last=5)
        await s.tap(*c, "Confirm")
        s.snap(a[0], "admin-order", last=1)
        await s.tap(*a, "Confirmed")
        await s.tap(*a, "Shipped")
        s.snap(c[0], "status-update", last=3)
        await engine.dispose()

    return {
        "shop_name": settings.shop_name,
        "date": START.strftime("%Y-%m-%d"),
        "users": {
            "customer": {"id": CUSTOMER_ID, "name": CUSTOMER_NAME},
            "admin": {"id": ADMIN_ID, "name": "Sam Admin"},
        },
        "events": s.session.events,
    }


def main() -> None:
    transcript = asyncio.run(run_scenario())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(transcript['events'])} events to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
