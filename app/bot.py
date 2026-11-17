"""Dispatcher / bot construction (kept separate from main so tests can reuse it)."""
from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, ErrorEvent
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.handlers import build_router
from app.i18n import t
from app.middlewares import DbMiddleware

log = logging.getLogger(__name__)


def build_dispatcher(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> Dispatcher:
    # Extra kwargs become workflow data, injectable into handlers by name.
    dp = Dispatcher(storage=MemoryStorage(), settings=settings, sessionmaker=sessionmaker)
    dp.update.outer_middleware(DbMiddleware(sessionmaker))
    dp.include_router(build_router())

    @dp.errors()
    async def on_error(event: ErrorEvent, lang: str = "en") -> bool:
        log.exception("unhandled error while processing update", exc_info=event.exception)
        update = event.update
        try:
            if update.message:
                await update.message.answer(t(lang, "error_generic"))
            elif update.callback_query:
                await update.callback_query.answer(t(lang, "error_generic"), show_alert=True)
        except Exception:  # never let the error handler itself crash polling
            log.exception("could not report error to user")
        return True

    return dp


async def set_commands(bot: Bot, settings: Settings) -> None:
    """Register the slash-command menus (customers see theirs, admins see more)."""
    customer = [
        BotCommand(command="start", description="Main menu"),
        BotCommand(command="catalog", description="Browse products"),
        BotCommand(command="cart", description="Your cart"),
        BotCommand(command="language", description="Language / Язык"),
        BotCommand(command="help", description="Help"),
    ]
    admin = customer + [
        BotCommand(command="orders", description="Orders by status"),
        BotCommand(command="products", description="Manage products"),
        BotCommand(command="add_product", description="Add a product"),
        BotCommand(command="edit_product", description="Edit a product"),
        BotCommand(command="stats", description="Orders and revenue"),
        BotCommand(command="broadcast", description="Message all users"),
    ]
    await bot.set_my_commands(customer)
    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(admin, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as exc:  # admin has not started the bot yet: chat not found
            log.info("admin menu for %s not set yet (%s)", admin_id, exc)
