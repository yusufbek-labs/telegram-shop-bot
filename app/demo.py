"""Public demo mode: visitors try the shop, orders are limited, and old demo data is cleaned up."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import utcnow
from app.notifications import notify_customer_status
from app.repositories import OrderRepo
from app.services.orders import OrderService, allowed_next
from app.services.permissions import is_admin

if TYPE_CHECKING:
    from app.sheets import SheetsSync

log = logging.getLogger(__name__)

KEEP_DAYS = 7
CLEANUP_EVERY_SECONDS = 24 * 3600

_tasks: set[asyncio.Task] = set()
_sleep = asyncio.sleep  # tests replace this to skip the wait


async def limit_reached(session: AsyncSession, settings: Settings, user_id: int) -> bool:
    """True when a visitor has already placed the day's quota of orders. The owner is never limited."""
    if not settings.demo_mode or is_admin(user_id, settings.admin_ids):
        return False
    since = utcnow() - timedelta(days=1)
    return await OrderRepo(session).count_since(user_id, since) >= settings.demo_max_orders_per_day


async def purge_old_orders(sessionmaker: async_sessionmaker[AsyncSession], keep_days: int = KEEP_DAYS) -> int:
    """Delete orders (and their lines) older than keep_days so the demo database stays small."""
    async with sessionmaker() as session:
        repo = OrderRepo(session)
        old = await repo.older_than(utcnow() - timedelta(days=keep_days))
        for order in old:
            await repo.delete(order)
        await session.commit()
    if old:
        log.info("demo: deleted %s orders older than %s days", len(old), keep_days)
    return len(old)


async def run_cleanup(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    """On startup and then once a day."""
    while True:
        try:
            await purge_old_orders(sessionmaker)
        except Exception:
            log.exception("demo: cleanup failed")
        await _sleep(CLEANUP_EVERY_SECONDS)


async def advance_order(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], order_id: int, expected: str,
                        sheets: SheetsSync | None = None) -> bool:
    """Move an order one step forward (never to cancelled) if nobody has touched it meanwhile."""
    async with sessionmaker() as session:
        order = await OrderRepo(session).get(order_id)
        if order is None or order.status != expected:
            return False
        step = next((s for s in allowed_next(expected) if s != "cancelled"), None)
        if step is None:
            return False
        order = await OrderService(session).apply_status(order_id, step)
        await session.commit()
        if sheets is not None:
            sheets.order_status_changed(order.id, order.status)
        log.info("demo: order %s -> %s", order.id, order.status)
        await notify_customer_status(bot, session, order)
        return True


def schedule_status_advance(bot: Bot, sessionmaker: async_sessionmaker[AsyncSession], settings: Settings,
                            order_id: int, status: str, sheets: SheetsSync | None = None) -> None:
    if settings.demo_status_seconds <= 0:
        return

    async def job() -> None:
        await _sleep(settings.demo_status_seconds)
        try:
            await advance_order(bot, sessionmaker, order_id, status, sheets)
        except Exception:
            log.exception("demo: could not advance order %s", order_id)

    task = asyncio.get_running_loop().create_task(job())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    if _tasks:
        await asyncio.wait(set(_tasks))


def cancel_pending() -> None:
    for task in set(_tasks):
        task.cancel()
