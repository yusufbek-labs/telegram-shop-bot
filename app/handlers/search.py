"""Product search: /search, the menu button, and the query step."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import Menu
from app.config import Settings
from app.handlers.catalog import MAX_CARDS
from app.handlers.common import send_product_cards
from app.i18n import t
from app.keyboards import customer as kb
from app.services.catalog import search_products
from app.services.validation import clean_query
from app.states import Search

router = Router(name="search")

TEXT = F.text & ~F.text.startswith("/")


async def _ask(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Search.query)
    await message.answer(t(lang, "search_prompt"))


async def _search(message: Message, query: str, state: FSMContext, lang: str, session: AsyncSession,
                  settings: Settings) -> None:
    query = clean_query(query)
    if query is None:
        await message.answer(t(lang, "search_invalid"))
        return
    await state.clear()
    found = await search_products(session, query)
    shown = found[:MAX_CARDS]
    safe_query = escape(query)
    if not found:
        await message.answer(t(lang, "search_nothing", query=safe_query), reply_markup=kb.after_search(lang))
        return
    await message.answer(t(lang, "search_header", query=safe_query, count=len(found)))
    await send_product_cards(message, lang, shown, settings.currency_symbol)
    if len(found) > len(shown):
        footer = t(lang, "search_footer_more", query=safe_query, shown=len(shown), count=len(found))
    else:
        footer = t(lang, "search_footer", query=safe_query, count=len(shown))
    await message.answer(footer, reply_markup=kb.after_search(lang))


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject, state: FSMContext, lang: str,
                     session: AsyncSession, settings: Settings) -> None:
    await state.clear()
    if command.args:
        await _search(message, command.args, state, lang, session, settings)
    else:
        await _ask(message, state, lang)


@router.callback_query(Menu.filter(F.action == "search"))
async def open_search(cb: CallbackQuery, state: FSMContext, lang: str) -> None:
    await cb.answer()
    await _ask(cb.message, state, lang)


@router.message(Search.query, TEXT)
async def got_query(message: Message, state: FSMContext, lang: str, session: AsyncSession,
                    settings: Settings) -> None:
    await _search(message, message.text, state, lang, session, settings)
