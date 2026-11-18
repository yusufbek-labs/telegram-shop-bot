"""Checkout FSM: name -> phone -> address -> payment -> (bank receipt) -> confirmation."""
from __future__ import annotations

import logging
from html import escape
from typing import TYPE_CHECKING

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Document, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import CartAct, Confirm, Pay
from app.config import Settings
from app.formatting import lines_text, payment_label, receipt_line
from app.handlers.common import notify_admins_new_order, show
from app.i18n import t
from app.keyboards import customer as kb
from app.services.cart import CartService, CartView
from app.services.money import format_money
from app.services.orders import CheckoutData, CartChangedError, EmptyCartError, OrderService
from app.services.validation import clean_address, clean_name, clean_phone
from app.states import Checkout

if TYPE_CHECKING:
    from app.sheets import SheetsSync

log = logging.getLogger(__name__)
router = Router(name="checkout")

TEXT = F.text & ~F.text.startswith("/")


@router.callback_query(CartAct.filter(F.action == "checkout"))
async def start_checkout(cb: CallbackQuery, state: FSMContext, lang: str, session: AsyncSession) -> None:
    view = await CartService(session).view(cb.from_user.id)
    if view.is_empty:
        await cb.answer(t(lang, "cart_empty"), show_alert=True)
        return
    await state.set_state(Checkout.name)
    await cb.answer()
    await cb.message.answer(t(lang, "checkout_name"))


@router.message(Checkout.name, TEXT)
async def got_name(message: Message, state: FSMContext, lang: str) -> None:
    name = clean_name(message.text)
    if name is None:
        await message.answer(t(lang, "invalid_name"))
        return
    await state.update_data(name=name)
    await state.set_state(Checkout.phone)
    await message.answer(t(lang, "checkout_phone"), reply_markup=kb.phone_request(lang))


@router.message(Checkout.phone, F.contact)
async def got_contact(message: Message, state: FSMContext, lang: str) -> None:
    await _save_phone(message, state, lang, message.contact.phone_number)


@router.message(Checkout.phone, TEXT)
async def got_phone_text(message: Message, state: FSMContext, lang: str) -> None:
    await _save_phone(message, state, lang, message.text)


async def _save_phone(message: Message, state: FSMContext, lang: str, raw: str) -> None:
    phone = clean_phone(raw)
    if phone is None:
        await message.answer(t(lang, "invalid_phone"))
        return
    await state.update_data(phone=phone)
    await state.set_state(Checkout.address)
    await message.answer(t(lang, "checkout_address"), reply_markup=ReplyKeyboardRemove())


@router.message(Checkout.address, TEXT)
async def got_address(message: Message, state: FSMContext, lang: str, settings: Settings) -> None:
    address = clean_address(message.text)
    if address is None:
        await message.answer(t(lang, "invalid_address"))
        return
    await state.update_data(address=address)
    await state.set_state(Checkout.payment)
    await message.answer(t(lang, "checkout_payment"), reply_markup=kb.payment(lang, bool(settings.payment_details)))


@router.callback_query(Checkout.payment, Pay.filter())
async def got_payment(cb: CallbackQuery, callback_data: Pay, state: FSMContext, lang: str,
                      session: AsyncSession, settings: Settings) -> None:
    method = callback_data.method
    if method == "transfer" and not settings.payment_details:  # option switched off since the button was sent
        await cb.answer(t(lang, "stale_button"), show_alert=True)
        return
    view = await _cart_view(cb, state, lang, session)
    if view is None:
        return
    await state.update_data(payment=method, receipt_file_id=None, receipt_type=None)
    if method == "transfer":
        await state.set_state(Checkout.receipt)
        await show(cb, t(lang, "checkout_receipt", details=escape(settings.payment_details),
                         total=format_money(view.total_cents, settings.currency_symbol)))
        return
    await _show_summary(cb, view, state, lang, settings)


async def _cart_view(event: Message | CallbackQuery, state: FSMContext, lang: str,
                     session: AsyncSession) -> CartView | None:
    """The cart, or None (after telling the user) if it was emptied while the form was open."""
    view = await CartService(session).view(event.from_user.id)
    if view.is_empty:
        await state.clear()
        await show(event, t(lang, "cart_empty"), kb.back_to_menu(lang))
        return None
    return view


async def _show_summary(event: Message | CallbackQuery, view: CartView, state: FSMContext, lang: str,
                        settings: Settings) -> None:
    data = await state.get_data()
    await state.set_state(Checkout.confirm)
    summary = t(
        lang, "checkout_summary",
        items=lines_text(lang, view.lines, settings.currency_symbol),
        total=format_money(view.total_cents, settings.currency_symbol),
        name=escape(data["name"]), phone=escape(data["phone"]), address=escape(data["address"]),
        payment=payment_label(lang, data["payment"]),
        receipt=receipt_line(lang, bool(data.get("receipt_file_id"))),
    )
    await show(event, summary, kb.confirm(lang, "checkout"))


def _is_receipt_document(document: Document) -> bool:
    mime = document.mime_type or ""
    return mime == "application/pdf" or mime.startswith("image/")


async def _save_receipt(message: Message, file_id: str, kind: str, state: FSMContext, lang: str,
                        session: AsyncSession, settings: Settings) -> None:
    view = await _cart_view(message, state, lang, session)
    if view is None:
        return
    await state.update_data(receipt_file_id=file_id, receipt_type=kind)
    await _show_summary(message, view, state, lang, settings)


@router.message(Checkout.receipt, F.photo)
async def got_receipt_photo(message: Message, state: FSMContext, lang: str, session: AsyncSession,
                            settings: Settings) -> None:
    await _save_receipt(message, message.photo[-1].file_id, "photo", state, lang, session, settings)


@router.message(Checkout.receipt, F.document)
async def got_receipt_document(message: Message, state: FSMContext, lang: str, session: AsyncSession,
                               settings: Settings) -> None:
    if not _is_receipt_document(message.document):
        await message.answer(t(lang, "receipt_invalid"))
        return
    await _save_receipt(message, message.document.file_id, "document", state, lang, session, settings)


@router.message(Checkout.receipt, ~F.text.startswith("/"))
async def wrong_receipt(message: Message, lang: str) -> None:
    await message.answer(t(lang, "receipt_invalid"))


@router.callback_query(Checkout.confirm, Confirm.filter(F.ctx == "checkout"))
async def confirm_order(cb: CallbackQuery, callback_data: Confirm, state: FSMContext, lang: str,
                        session: AsyncSession, settings: Settings, bot: Bot,
                        sheets: SheetsSync | None = None) -> None:
    if not callback_data.ok:
        await state.clear()
        await show(cb, t(lang, "checkout_cancelled"), kb.main_menu(lang))
        return
    data = await state.get_data()
    try:
        order = await OrderService(session).checkout(
            cb.from_user.id,
            CheckoutData(data["name"], data["phone"], data["address"], data["payment"],
                         data.get("receipt_file_id"), data.get("receipt_type")),
        )
    except (EmptyCartError, CartChangedError):
        await state.clear()
        await show(cb, t(lang, "cart_changed"), kb.back_to_menu(lang))
        return
    await state.clear()
    await show(
        cb,
        t(lang, "order_placed", id=order.id, total=format_money(order.total_cents, settings.currency_symbol)),
        kb.main_menu(lang),
    )
    await session.commit()  # persist before admins can tap status buttons
    log.info("order %s placed by %s total=%s", order.id, cb.from_user.id, order.total_cents)
    if sheets is not None:
        sheets.order_created(order)
    await notify_admins_new_order(bot, session, settings, order)
