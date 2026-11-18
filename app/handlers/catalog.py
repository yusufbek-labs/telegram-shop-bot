"""Catalog browsing and product cards."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import AddToCart, Cat, Menu
from app.config import Settings
from app.handlers.common import send_product_cards, show
from app.i18n import t
from app.keyboards import customer as kb
from app.repositories import CatalogRepo
from app.services.cart import CartService, ProductUnavailable

router = Router(name="catalog")

MAX_CARDS = 10  # keep a category page from flooding the chat


async def _show_categories(event: Message | CallbackQuery, lang: str, session: AsyncSession) -> None:
    cats = await CatalogRepo(session).categories()
    if not cats:
        await show(event, t(lang, "catalog_empty"), kb.back_to_menu(lang))
        return
    await show(event, t(lang, "catalog_title"), kb.categories(lang, cats))


@router.message(Command("catalog"))
async def cmd_catalog(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    await state.clear()
    await _show_categories(message, lang, session)


@router.callback_query(Menu.filter(F.action == "catalog"))
async def open_catalog(cb: CallbackQuery, lang: str, session: AsyncSession) -> None:
    await _show_categories(cb, lang, session)


@router.callback_query(Cat.filter())
async def open_category(cb: CallbackQuery, callback_data: Cat, lang: str, session: AsyncSession,
                        settings: Settings) -> None:
    repo = CatalogRepo(session)
    category = await repo.category(callback_data.id)
    products = (await repo.products(callback_data.id))[:MAX_CARDS] if category else []
    await cb.answer()
    target = cb.message
    if category is None or not products:
        await show(cb, t(lang, "category_empty"), kb.after_products(lang), answer=False)
        return
    await target.answer(t(lang, "category_header", category=category.name(lang)))
    await send_product_cards(target, lang, products, settings.currency_symbol)
    await target.answer(
        t(lang, "category_footer", category=category.name(lang), count=len(products)),
        reply_markup=kb.after_products(lang),
    )


@router.callback_query(AddToCart.filter())
async def add_to_cart(cb: CallbackQuery, callback_data: AddToCart, lang: str, session: AsyncSession) -> None:
    try:
        product = await CartService(session).add(cb.from_user.id, callback_data.product_id)
    except ProductUnavailable:
        await cb.answer(t(lang, "product_unavailable"), show_alert=True)
        return
    await cb.answer(t(lang, "added_to_cart", name=product.name))
