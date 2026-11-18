"""Shared handler helpers."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import Order, Product
from app.formatting import order_card, product_card
from app.i18n import t
from app.keyboards import admin as admin_kb
from app.keyboards import customer as customer_kb
from app.repositories import UserRepo
from app.services.permissions import is_admin

log = logging.getLogger(__name__)

ADMIN_COMMANDS = {"orders", "products", "add_product", "edit_product", "categories", "stats", "broadcast"}
CAPTION_LIMIT = 1024  # Telegram's cap on photo / document captions


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
            if msg.photo or msg.document:
                await msg.edit_caption(caption=text, reply_markup=markup)
            else:
                await msg.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            # e.g. "message is not modified" or a caption that got too long: send a fresh one
            await msg.answer(text, reply_markup=markup)
    else:
        await event.bot.send_message(event.from_user.id, text, reply_markup=markup)
    if answer:
        await event.answer()


async def send_product_cards(target: Message, lang: str, products: list[Product], symbol: str) -> None:
    for p in products:
        text = product_card(lang, p, symbol)
        markup = customer_kb.product_card_kb(lang, p.id)
        if p.image_url:
            try:
                await target.answer_photo(p.image_url, caption=text, reply_markup=markup)
                continue
            except TelegramBadRequest:
                log.warning("bad image url for product %s, falling back to text", p.id)
        await target.answer(text, reply_markup=markup)


async def send_receipt(bot: Bot, chat_id: int, order: Order, caption: str,
                       markup: InlineKeyboardMarkup | None = None, reply_to: int | None = None) -> None:
    """Send the order's stored receipt (a Telegram file_id) as a photo or a document."""
    if order.receipt_type == "photo":
        await bot.send_photo(chat_id, order.receipt_file_id, caption=caption, reply_markup=markup,
                             reply_to_message_id=reply_to)
    else:
        await bot.send_document(chat_id, order.receipt_file_id, caption=caption, reply_markup=markup,
                                reply_to_message_id=reply_to)


async def send_order_card(bot: Bot, chat_id: int, lang: str, settings: Settings, order: Order,
                          header: str = "") -> None:
    """The new-order message the shop owner gets: summary with status buttons, receipt attached if any."""
    text = t(lang, "admin_new_order", id=order.id,
             details=order_card(lang, order, settings.currency_symbol).split("\n", 1)[1])
    if header:
        text = f"{header}\n\n{text}"
    markup = admin_kb.order_actions(lang, order)
    try:
        if not order.receipt_file_id:
            await bot.send_message(chat_id, text, reply_markup=markup)
        elif len(text) <= CAPTION_LIMIT:
            await send_receipt(bot, chat_id, order, text, markup)
        else:  # too long for a caption: summary with buttons first, then the receipt under it
            sent = await bot.send_message(chat_id, text, reply_markup=markup)
            await send_receipt(bot, chat_id, order, t(lang, "receipt_caption", id=order.id),
                               reply_to=sent.message_id)
    except TelegramAPIError as exc:  # an admin who never opened the bot cannot be messaged
        log.warning("cannot send the order card to %s: %s", chat_id, exc)


async def notify_admins_new_order(bot: Bot, session: AsyncSession, settings: Settings, order) -> None:
    users = UserRepo(session)
    for admin_id in settings.admin_ids:
        admin = await users.get(admin_id)
        await send_order_card(bot, admin_id, admin.language if admin else "en", settings, order)
