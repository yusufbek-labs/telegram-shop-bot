"""Admin /stats and /broadcast."""
from __future__ import annotations

import asyncio
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.callbacks import Confirm
from app.config import Settings
from app.handlers.common import IsAdmin, show
from app.i18n import t
from app.keyboards import customer as ckb
from app.repositories import UserRepo
from app.services.broadcast import RateLimiter, broadcast
from app.services.money import format_money
from app.services.stats import StatsService
from app.states import Broadcast

log = logging.getLogger(__name__)
router = Router(name="admin_misc")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

# Keep references so background broadcasts are not garbage collected mid-flight.
_background: set[asyncio.Task] = set()


@router.message(Command("stats"))
async def cmd_stats(message: Message, state: FSMContext, lang: str, session: AsyncSession, settings: Settings) -> None:
    await state.clear()
    s = await StatsService(session, settings.timezone).compute()
    sym = settings.currency_symbol
    await message.answer(
        t(lang, "stats", t_orders=s.today_orders, t_rev=format_money(s.today_revenue_cents, sym),
          w_orders=s.week_orders, w_rev=format_money(s.week_revenue_cents, sym))
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    await state.clear()
    count = len(await UserRepo(session).active_ids())
    if count == 0:
        await message.answer(t(lang, "broadcast_no_users"))
        return
    await state.set_state(Broadcast.text)
    await message.answer(t(lang, "broadcast_ask", count=count))


@router.message(Broadcast.text, F.text & ~F.text.startswith("/"))
async def broadcast_text(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    count = len(await UserRepo(session).active_ids())
    # Store the plain text; it is escaped when sent so admins cannot break HTML by accident.
    await state.update_data(text=message.text)
    await state.set_state(Broadcast.confirm)
    await message.answer(
        t(lang, "broadcast_preview", text=escape(message.text), count=count),
        reply_markup=ckb.confirm(lang, "broadcast"),
    )


@router.callback_query(Broadcast.confirm, Confirm.filter(F.ctx == "broadcast"))
async def broadcast_confirm(cb: CallbackQuery, callback_data: Confirm, state: FSMContext, lang: str,
                            session: AsyncSession, settings: Settings, bot: Bot,
                            sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    data = await state.get_data()
    await state.clear()
    if not callback_data.ok:
        await show(cb, t(lang, "broadcast_cancelled"))
        return
    ids = await UserRepo(session).active_ids()
    await show(cb, t(lang, "broadcast_started"))
    task = asyncio.create_task(_run(bot, sessionmaker, ids, escape(data["text"]), settings, cb.from_user.id, lang))
    _background.add(task)
    task.add_done_callback(_background.discard)


async def _run(bot: Bot, sessionmaker, ids: list[int], text: str, settings: Settings, admin_id: int, lang: str) -> None:
    async def mark_blocked(uid: int) -> None:
        async with sessionmaker() as s:
            await UserRepo(s).mark_blocked(uid)
            await s.commit()

    result = await broadcast(bot, ids, text, RateLimiter(settings.broadcast_rate), on_blocked=mark_blocked)
    log.info("broadcast done: %s", result)
    await bot.send_message(
        admin_id, t(lang, "broadcast_done", sent=result.sent, blocked=result.blocked, failed=result.failed)
    )
