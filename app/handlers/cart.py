"""Cart view and quantity controls."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import CartAct, Menu
from app.config import Settings
from app.formatting import cart_text
from app.handlers.common import show
from app.i18n import t
from app.keyboards import customer as kb
from app.services.cart import CartService

router = Router(name="cart")


async def render_cart(event: Message | CallbackQuery, lang: str, session: AsyncSession, settings: Settings,
                      user_id: int, answer: bool = True) -> None:
    view = await CartService(session).view(user_id)
    await show(event, cart_text(lang, view, settings.currency_symbol), kb.cart(lang, view.lines), answer=answer)


@router.message(Command("cart"))
async def cmd_cart(message: Message, state: FSMContext, lang: str, session: AsyncSession, settings: Settings) -> None:
    await state.clear()
    await render_cart(message, lang, session, settings, message.from_user.id)


@router.callback_query(Menu.filter(F.action == "cart"))
async def open_cart(cb: CallbackQuery, lang: str, session: AsyncSession, settings: Settings) -> None:
    await render_cart(cb, lang, session, settings, cb.from_user.id)


@router.callback_query(CartAct.filter(F.action.in_({"inc", "dec", "del", "clear", "noop"})))
async def cart_action(cb: CallbackQuery, callback_data: CartAct, lang: str, session: AsyncSession,
                      settings: Settings) -> None:
    svc = CartService(session)
    uid, pid = cb.from_user.id, callback_data.product_id
    if callback_data.action == "inc":
        await svc.change_quantity(uid, pid, +1)
    elif callback_data.action == "dec":
        await svc.change_quantity(uid, pid, -1)
    elif callback_data.action == "del":
        await svc.remove(uid, pid)
    elif callback_data.action == "clear":
        await svc.clear(uid)
        await cb.answer(t(lang, "cart_cleared"))
        await render_cart(cb, lang, session, settings, uid, answer=False)
        return
    else:
        await cb.answer()
        return
    await render_cart(cb, lang, session, settings, uid)
