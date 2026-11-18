"""Admin order management: /orders, order cards and status buttons."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import OrderOpen, OrderReceipt, OrdersFilter, OrderStatusCb
from app.config import Settings
from app.formatting import order_card, status_label
from app.handlers.common import IsAdmin, notify_customer_status, send_receipt, show
from app.i18n import t
from app.keyboards import admin as akb
from app.repositories import OrderRepo
from app.services.orders import STATUSES, InvalidTransition, OrderNotFound, OrderService
from app.services.permissions import PermissionDenied

if TYPE_CHECKING:
    from app.sheets import SheetsSync

log = logging.getLogger(__name__)

router = Router(name="admin_orders")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

# Not admin-filtered on purpose: OrderService.change_status enforces permissions itself,
# so a forged or leaked button from a non-admin gets a clear "no permission" answer.
status_router = Router(name="order_status")


async def _show_list(event, lang: str, session: AsyncSession, settings: Settings, status: str | None) -> None:
    orders = await OrderRepo(session).list(status=status, limit=10)
    label = t(lang, "filter_all") if status is None else status_label(lang, status)
    if not orders:
        await show(event, f"{t(lang, 'admin_no_orders')}", akb.orders_filter(lang))
        return
    await show(
        event,
        t(lang, "admin_orders_list", status=label, count=len(orders)),
        akb.orders_list(lang, orders, settings.currency_symbol),
    )


@router.message(Command("orders"))
async def cmd_orders(message: Message, command: CommandObject, state: FSMContext, lang: str,
                     session: AsyncSession, settings: Settings) -> None:
    await state.clear()
    arg = (command.args or "").strip().lower()
    if arg in STATUSES or arg == "all":
        await _show_list(message, lang, session, settings, None if arg == "all" else arg)
        return
    await message.answer(t(lang, "admin_orders_title"), reply_markup=akb.orders_filter(lang))


@router.callback_query(OrdersFilter.filter())
async def orders_filter(cb: CallbackQuery, callback_data: OrdersFilter, lang: str, session: AsyncSession,
                        settings: Settings) -> None:
    status = callback_data.status
    if status == "menu":
        await show(cb, t(lang, "admin_orders_title"), akb.orders_filter(lang))
    elif status == "all" or status in STATUSES:
        await _show_list(cb, lang, session, settings, None if status == "all" else status)
    else:
        await cb.answer(t(lang, "stale_button"))


@router.callback_query(OrderOpen.filter())
async def open_order(cb: CallbackQuery, callback_data: OrderOpen, lang: str, session: AsyncSession,
                     settings: Settings) -> None:
    order = await OrderRepo(session).get(callback_data.order_id)
    if order is None:
        await cb.answer(t(lang, "order_not_found"), show_alert=True)
        return
    await show(cb, order_card(lang, order, settings.currency_symbol), akb.order_actions(lang, order))


@router.callback_query(OrderReceipt.filter())
async def open_receipt(cb: CallbackQuery, callback_data: OrderReceipt, lang: str, session: AsyncSession,
                       bot: Bot) -> None:
    order = await OrderRepo(session).get(callback_data.order_id)
    if order is None:
        await cb.answer(t(lang, "order_not_found"), show_alert=True)
    elif not order.receipt_file_id:
        await cb.answer(t(lang, "receipt_missing"), show_alert=True)
    else:
        await cb.answer()
        await send_receipt(bot, cb.from_user.id, order, t(lang, "receipt_caption", id=order.id))


@status_router.callback_query(OrderStatusCb.filter())
async def change_status(cb: CallbackQuery, callback_data: OrderStatusCb, lang: str, session: AsyncSession,
                        settings: Settings, bot: Bot, sheets: SheetsSync | None = None) -> None:
    try:
        order = await OrderService(session).change_status(
            callback_data.order_id, callback_data.status, cb.from_user.id, settings.admin_ids
        )
    except PermissionDenied:
        log.warning("user %s tried to change order status without permission", cb.from_user.id)
        await cb.answer(t(lang, "no_permission"), show_alert=True)
        return
    except OrderNotFound:
        await cb.answer(t(lang, "order_not_found"), show_alert=True)
        return
    except InvalidTransition:
        # Usually a stale button (another admin already moved the order).
        await cb.answer(t(lang, "status_not_allowed"), show_alert=True)
        current = await OrderRepo(session).get(callback_data.order_id)
        if current is not None:
            await show(cb, order_card(lang, current, settings.currency_symbol), akb.order_actions(lang, current),
                       answer=False)
        return

    log.info("order %s -> %s by admin %s", order.id, order.status, cb.from_user.id)
    await cb.answer(t(lang, "status_changed", id=order.id, status=status_label(lang, order.status)))
    await show(cb, order_card(lang, order, settings.currency_symbol), akb.order_actions(lang, order), answer=False)
    if sheets is not None:
        sheets.order_status_changed(order.id, order.status)
    await notify_customer_status(bot, session, order)
