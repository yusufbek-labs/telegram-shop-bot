"""Background Google Sheets work: order log, menu import and status import.

Nothing here may break the shop: every sheet call is made off the request path, failures are retried
and then logged, and the database stays the source of truth for orders.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import Order
from app.handlers.common import notify_customer_status
from app.repositories import OrderRepo
from app.services.orders import STATUSES, InvalidTransition, OrderService
from app.sheets.backend import (
    MENU_HEADER,
    MENU_TAB,
    ORDER_ID_COL,
    ORDERS_HEADER,
    ORDERS_TAB,
    STATUS_COL,
    SheetBackend,
)
from app.sheets.menu import apply_menu, export_menu
from app.sheets.rows import order_row

log = logging.getLogger(__name__)

DEFAULT_RETRY_DELAYS = (2.0, 10.0, 30.0)


class SheetsSync:
    def __init__(self, backend: SheetBackend, settings: Settings,
                 retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS):
        self.backend = backend
        self.settings = settings
        self.retry_delays = retry_delays
        self.tz = ZoneInfo(settings.timezone)
        self._lock = asyncio.Lock()  # one sheet call at a time: the gspread client is not thread safe
        self._pending: set[asyncio.Task] = set()

    async def _call(self, func: Callable, *args):
        async with self._lock:
            return await asyncio.to_thread(func, *args)

    def _submit(self, label: str, job: Callable) -> None:
        task = asyncio.get_running_loop().create_task(self._run(label, job))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _run(self, label: str, job: Callable) -> None:
        attempts = len(self.retry_delays) + 1
        for attempt in range(1, attempts + 1):
            try:
                await job()
                return
            except Exception as exc:
                if attempt == attempts:
                    log.error("sheets: giving up on %s after %s attempts: %s", label, attempts, exc)
                    return
                delay = self.retry_delays[attempt - 1]
                log.warning("sheets: %s failed (%s), retry %s/%s in %ss", label, exc, attempt, attempts - 1, delay)
                await asyncio.sleep(delay)

    async def drain(self, timeout: float | None = None) -> None:
        """Wait for queued writes (used on shutdown and in tests)."""
        if self._pending:
            await asyncio.wait(set(self._pending), timeout=timeout)

    # --- bot -> sheet -------------------------------------------------------------------------

    def order_created(self, order: Order) -> None:
        """Queue the order row. Call after the order is committed; never raises."""
        try:
            row = order_row(order, self.tz)
        except Exception:
            log.exception("sheets: could not build the row for order %s", order.id)
            return

        async def job() -> None:
            await self._call(self.backend.ensure_tab, ORDERS_TAB, ORDERS_HEADER)
            await self._call(self.backend.append_rows, ORDERS_TAB, [row])

        self._submit(f"order {order.id}", job)

    def order_status_changed(self, order_id: int, status: str) -> None:
        """Queue the new status for the order's row (the admin used a bot button)."""

        async def job() -> None:
            rows = await self._call(self.backend.read_rows, ORDERS_TAB)
            row = _find_order_row(rows, order_id)
            if row is not None:
                await self._call(self.backend.update_cell, ORDERS_TAB, row, STATUS_COL, status)

        self._submit(f"status of order {order_id}", job)

    # --- sheet -> bot -------------------------------------------------------------------------

    async def run_forever(self, bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        interval = self.settings.sheets_sync_seconds
        log.info("sheets: syncing every %ss (menu=%s)", interval, self.settings.sheets_menu_sync)
        while True:
            await self.sync_once(bot, sessionmaker)
            await asyncio.sleep(interval)

    async def sync_once(self, bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        if self.settings.sheets_menu_sync:
            try:
                await self.sync_menu(sessionmaker)
            except Exception as exc:
                log.error("sheets: menu sync failed: %s", exc)
        if self._pending:  # a status write is still on its way; reading now would see the old value
            return
        try:
            await self.sync_statuses(bot, sessionmaker)
        except Exception as exc:
            log.error("sheets: status sync failed: %s", exc)

    async def sync_menu(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        await self._call(self.backend.ensure_tab, MENU_TAB, MENU_HEADER)
        rows = await self._call(self.backend.read_rows, MENU_TAB)
        async with sessionmaker() as session:
            if len(rows) <= 1:  # a new, empty tab: start it from the current catalog
                exported = await export_menu(session)
                if exported:
                    await self._call(self.backend.append_rows, MENU_TAB, exported)
                    log.info("sheets: filled the empty Menu tab with %s products", len(exported))
                return
            report = await apply_menu(session, rows)
            await session.commit()
        if report.created or report.updated or report.hidden or report.skipped:
            log.info("sheets: menu synced, %s", report)

    async def sync_statuses(self, bot: Bot, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        rows = await self._call(self.backend.read_rows, ORDERS_TAB)
        async with sessionmaker() as session:
            for number, row in enumerate(rows[1:], start=2):
                wanted = _cell(row, STATUS_COL).casefold()
                order_id = _order_id(_cell(row, ORDER_ID_COL))
                if not wanted or order_id is None:
                    continue
                order = await OrderRepo(session).get(order_id)
                if order is None:
                    log.warning("sheets: Orders row %s refers to unknown order %r", number, row[ORDER_ID_COL - 1])
                    continue
                if wanted == order.status:
                    continue
                try:
                    if wanted not in STATUSES:
                        raise ValueError(f"unknown status {wanted!r}")
                    order = await OrderService(session).apply_status(order_id, wanted)
                except (ValueError, InvalidTransition) as exc:
                    log.warning("sheets: ignored status %r for order %s (now %s): %s",
                                _cell(row, STATUS_COL), order_id, order.status, exc)
                    await self._call(self.backend.update_cell, ORDERS_TAB, number, STATUS_COL, order.status)
                    continue
                await session.commit()
                log.info("order %s -> %s from the sheet", order.id, order.status)
                await notify_customer_status(bot, session, order)


def _cell(row: list[str], col: int) -> str:
    return row[col - 1].strip() if col <= len(row) else ""


def _order_id(text: str) -> int | None:
    try:
        return int(float(text))  # a sheet may hand integers back as "5.0"
    except ValueError:
        return None


def _find_order_row(rows: list[list[str]], order_id: int) -> int | None:
    for number, row in enumerate(rows[1:], start=2):
        if _order_id(_cell(row, ORDER_ID_COL)) == order_id:
            return number
    return None
