"""Messages the bot sends to customers on its own (not as a reply to their update)."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order
from app.formatting import status_label
from app.i18n import t
from app.repositories import UserRepo

log = logging.getLogger(__name__)


async def notify_customer_status(bot: Bot, session: AsyncSession, order: Order) -> None:
    customer = await UserRepo(session).get(order.user_id)
    lang = customer.language if customer else "en"
    try:
        await bot.send_message(
            order.user_id, t(lang, "order_status_update", id=order.id, status=status_label(lang, order.status))
        )
    except TelegramAPIError as exc:
        log.warning("could not notify customer %s: %s", order.user_id, exc)
