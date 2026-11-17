"""Shared handler helpers."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.formatting import order_card
from app.i18n import t
from app.keyboards import admin as admin_kb
from app.repositories import UserRepo
from app.services.permissions import is_admin

log = logging.getLogger(__name__)

ADMIN_COMMANDS = {"orders", "products", "add_product", "edit_product", "stats", "broadcast"}


class IsAdmin(BaseFilter):
    """Passes only for users listed in ADMIN_IDS."""

    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        user = getattr(event, "from_user", None)
        return is_admin(user.id if user else None, settings.admin_ids)


async def show(event: Message | CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None,
               answer: bool = True) -> None:
    """Reply to a message, or edit the message a callback button belongs to."""
    if isinstance(event, Message):
        await event.answer(text, reply_markup=markup)
        return
    msg = event.message
    if isinstance(msg, Message):
        try:
            await msg.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            # e.g. "message is not modified" or the message is a photo: send a fresh one
            await msg.answer(text, reply_markup=markup)
    else:
        await event.bot.send_message(event.from_user.id, text, reply_markup=markup)
    if answer:
        await event.answer()


async def notify_admins_new_order(bot: Bot, session: AsyncSession, settings: Settings, order) -> None:
    users = UserRepo(session)
    for admin_id in settings.admin_ids:
        admin = await users.get(admin_id)
        lang = admin.language if admin else "en"
        text = t(lang, "admin_new_order", id=order.id,
                 details=order_card(lang, order, settings.currency_symbol).split("\n", 1)[1])
        try:
            await bot.send_message(admin_id, text, reply_markup=admin_kb.order_actions(lang, order))
        except TelegramAPIError as exc:  # an admin who never opened the bot cannot be messaged
            log.warning("cannot notify admin %s: %s", admin_id, exc)
