"""/start, main menu, help, language switch, /cancel."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import Lang, Menu
from app.config import Settings
from app.i18n import LANGS, t
from app.keyboards import customer as kb
from app.repositories import OrderRepo, UserRepo
from app.handlers.common import show
from app.formatting import status_label
from app.services.money import format_money

router = Router(name="start")


def _help(lang: str, is_admin_user: bool) -> str:
    return t(lang, "help") + (t(lang, "help_admin") if is_admin_user else "")


@router.message(Command("start", "menu"))
async def cmd_start(message: Message, state: FSMContext, lang: str, settings: Settings) -> None:
    await state.clear()
    welcome = t(lang, "welcome", shop=settings.shop_name)
    if settings.demo_mode:
        welcome += f"\n\n{t(lang, 'demo_note')}"
    await message.answer(f"{welcome}\n\n{t(lang, 'menu_title')}:", reply_markup=kb.main_menu(lang))


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str, settings: Settings) -> None:
    is_admin_user = message.from_user.id in settings.admin_ids
    await message.answer(_help(lang, is_admin_user), reply_markup=kb.main_menu(lang))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await message.answer(t(lang, "cancelled"), reply_markup=ReplyKeyboardRemove())
    await message.answer(t(lang, "menu_title"), reply_markup=kb.main_menu(lang))


@router.message(Command("language"))
async def cmd_language(message: Message, lang: str) -> None:
    await message.answer(t(lang, "language_prompt"), reply_markup=kb.languages())


@router.callback_query(Lang.filter())
async def set_language(cb: CallbackQuery, callback_data: Lang, session: AsyncSession) -> None:
    if callback_data.code not in LANGS:
        await cb.answer(t("en", "stale_button"))
        return
    await UserRepo(session).set_language(cb.from_user.id, callback_data.code)
    new = callback_data.code
    await show(cb, f"{t(new, 'language_set')}\n\n{t(new, 'menu_title')}:", kb.main_menu(new))


@router.callback_query(Menu.filter(F.action.in_({"home", "help", "language", "orders"})))
async def menu_action(cb: CallbackQuery, callback_data: Menu, state: FSMContext, lang: str,
                      session: AsyncSession, settings: Settings) -> None:
    action = callback_data.action
    if action == "home":
        await state.clear()
        await show(cb, f"{t(lang, 'welcome', shop=settings.shop_name)}\n\n{t(lang, 'menu_title')}:", kb.main_menu(lang))
    elif action == "help":
        await show(cb, _help(lang, cb.from_user.id in settings.admin_ids), kb.back_to_menu(lang))
    elif action == "language":
        await show(cb, t(lang, "language_prompt"), kb.languages())
    else:  # orders
        orders = await OrderRepo(session).list(user_id=cb.from_user.id, limit=10)
        if not orders:
            await show(cb, t(lang, "my_orders_empty"), kb.back_to_menu(lang))
            return
        lines = [
            t(lang, "order_line", id=o.id, status=status_label(lang, o.status),
              total=format_money(o.total_cents, settings.currency_symbol))
            for o in orders
        ]
        await show(cb, t(lang, "my_orders_title") + "\n\n" + "\n".join(lines), kb.back_to_menu(lang))
