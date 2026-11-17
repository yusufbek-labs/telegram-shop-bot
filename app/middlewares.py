"""Per-update DB session, user bookkeeping and language resolution."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.i18n import resolve_lang
from app.repositories import UserRepo

log = logging.getLogger(__name__)


class DbMiddleware(BaseMiddleware):
    """Registered as an *outer* update middleware. Injects `session`, `user` and `lang`.

    The transaction commits when the handler returns and rolls back on error.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self.sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.sessionmaker() as session:
            data["session"] = session
            tg_user = data.get("event_from_user")
            data["lang"] = "en"
            if tg_user is not None and not tg_user.is_bot:
                user, created = await UserRepo(session).upsert(
                    tg_user.id, tg_user.username, tg_user.full_name, resolve_lang(tg_user.language_code)
                )
                if created:
                    log.info("new user %s (lang=%s)", user.id, user.language)
                data["user"] = user
                data["lang"] = user.language
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
