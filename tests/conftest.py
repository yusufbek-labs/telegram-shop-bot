"""Shared fixtures. Nothing here touches the network: Telegram is replaced by a recording fake session."""
from __future__ import annotations

import itertools
from collections.abc import AsyncGenerator
from datetime import datetime

import pytest
import pytest_asyncio
from aiogram import Bot, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageCaption, EditMessageText, SendDocument, SendMessage, SendPhoto
from aiogram.types import Chat, Message

from app.bot import build_dispatcher
from app import handlers as handler_pkg
from app.config import Settings
from app.db.session import create_engine_and_sessionmaker, init_db
from scripts.seed import seed

ADMIN_ID = 1000
CUSTOMER_ID = 2000


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None, bot_token="42:" + "A" * 35, admin_ids=[ADMIN_ID],
        db_path=str(tmp_path / "test.db"), broadcast_rate=30.0,
        payment_details="Example Bank\nIBAN: DE00 0000 0000 0000 00",
    )


@pytest_asyncio.fixture
async def sessionmaker(settings) -> AsyncGenerator:
    engine, sm = create_engine_and_sessionmaker(settings.db_url)
    await init_db(engine)
    yield sm
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(sessionmaker):
    await seed(sessionmaker)
    return sessionmaker


class FakeSession(BaseSession):
    """Records every Bot API call instead of sending it (the aiogram-documented testing approach)."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list = []
        self._ids = itertools.count(1)

    async def close(self) -> None:
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover - unused
        yield b""

    async def make_request(self, bot: Bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, (SendMessage, EditMessageText, EditMessageCaption, SendPhoto, SendDocument)):
            chat_id = getattr(method, "chat_id", 0) or 0
            return Message(
                message_id=next(self._ids), date=datetime.now(), chat=Chat(id=chat_id, type="private"),
                text=getattr(method, "text", None),
            )
        return True


def _release_routers() -> None:
    """Handler modules hold module-level routers, and aiogram lets a router join only one parent.
    The app builds its dispatcher once; tests build one per test, so detach the routers first."""
    import pkgutil
    from importlib import import_module

    for info in pkgutil.iter_modules(handler_pkg.__path__):
        module = import_module(f"app.handlers.{info.name}")
        for value in vars(module).values():
            if isinstance(value, Router):
                value._parent_router = None


class Harness:
    """Feeds raw updates into a real Dispatcher and exposes what the bot answered."""

    def __init__(self, settings: Settings, sessionmaker, sheets=None):
        self.session = FakeSession()
        self.bot = Bot(
            token=settings.bot_token, session=self.session, default=DefaultBotProperties(parse_mode="HTML")
        )
        _release_routers()
        self.dp = build_dispatcher(settings, sessionmaker, sheets)
        self._update_ids = itertools.count(1)

    @staticmethod
    def _user(uid: int, lang: str) -> dict:
        return {"id": uid, "is_bot": False, "first_name": f"User{uid}", "language_code": lang}

    def _message(self, uid: int, lang: str, text: str | None, **extra) -> dict:
        return {"message_id": next(self._update_ids), "date": 1_700_000_000,
                "chat": {"id": uid, "type": "private"}, "from": self._user(uid, lang), "text": text, **extra}

    async def say(self, uid: int, text: str, lang: str = "en") -> None:
        update = {"update_id": next(self._update_ids), "message": self._message(uid, lang, text)}
        await self.dp.feed_raw_update(self.bot, update)

    async def send_photo(self, uid: int, file_id: str = "photo-id", lang: str = "en") -> None:
        photo = [{"file_id": "small-" + file_id, "file_unique_id": "s", "width": 90, "height": 90},
                 {"file_id": file_id, "file_unique_id": "b", "width": 800, "height": 800}]
        update = {"update_id": next(self._update_ids), "message": self._message(uid, lang, None, photo=photo)}
        await self.dp.feed_raw_update(self.bot, update)

    async def send_document(self, uid: int, file_id: str = "doc-id", mime: str = "application/pdf",
                            lang: str = "en") -> None:
        document = {"file_id": file_id, "file_unique_id": "d", "file_name": "receipt", "mime_type": mime}
        update = {"update_id": next(self._update_ids), "message": self._message(uid, lang, None, document=document)}
        await self.dp.feed_raw_update(self.bot, update)

    async def press(self, uid: int, callback_data, lang: str = "en", on_photo: bool = False) -> None:
        """Press an inline button. on_photo=True means the button sits on a photo message with a caption."""
        extra = {"photo": [{"file_id": "p", "file_unique_id": "p", "width": 1, "height": 1}]} if on_photo else {}
        update = {
            "update_id": next(self._update_ids),
            "callback_query": {
                "id": str(next(self._update_ids)), "from": self._user(uid, lang), "chat_instance": "ci",
                "data": callback_data.pack(),
                "message": self._message(uid, lang, None if on_photo else "old", **extra),
            },
        }
        await self.dp.feed_raw_update(self.bot, update)

    def sent_to(self, chat_id: int) -> list[SendMessage]:
        kinds = (SendMessage, SendPhoto, SendDocument)
        return [c for c in self.session.calls if isinstance(c, kinds) and c.chat_id == chat_id]

    def caption_edits(self) -> list[EditMessageCaption]:
        return [c for c in self.session.calls if isinstance(c, EditMessageCaption)]

    def texts_to(self, chat_id: int) -> list[str]:
        return [getattr(c, "text", None) or getattr(c, "caption", "") for c in self.sent_to(chat_id)]

    def edits(self) -> list[EditMessageText]:
        return [c for c in self.session.calls if isinstance(c, EditMessageText)]

    def alerts(self) -> list[str]:
        return [c.text for c in self.session.calls if type(c).__name__ == "AnswerCallbackQuery" and c.text]

    def last_reply_text(self) -> str:
        """Last text the bot produced (new message or edit)."""
        for c in reversed(self.session.calls):
            if isinstance(c, (SendMessage, EditMessageText)):
                return c.text
        return ""


@pytest.fixture
def harness(settings, seeded) -> Harness:
    return Harness(settings, seeded)
