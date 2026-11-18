"""Admin category management: /categories list, add, rename and guarded delete."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import AdminNav, CategoryDelete, CategoryEdit, CategoryNew
from app.handlers.common import IsAdmin, show
from app.i18n import t
from app.keyboards import admin as akb
from app.repositories import CatalogRepo
from app.services.catalog import delete_category
from app.services.validation import clean_text
from app.states import CategoryForm

router = Router(name="admin_categories")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

TEXT = F.text & ~F.text.startswith("/")


async def _render(event: Message | CallbackQuery, lang: str, session: AsyncSession) -> None:
    cats = await CatalogRepo(session).categories()
    await show(event, t(lang, "admin_categories_title"), akb.categories_admin(lang, cats))


@router.message(Command("categories"))
async def cmd_categories(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    await state.clear()
    await _render(message, lang, session)


@router.callback_query(AdminNav.filter(F.section == "categories"))
async def categories_nav(cb: CallbackQuery, lang: str, session: AsyncSession) -> None:
    await _render(cb, lang, session)


@router.callback_query(CategoryNew.filter())
async def new_category(cb: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    await state.set_state(CategoryForm.name_en)
    await cb.answer()
    await cb.message.answer(t(lang, "category_ask_en"))


@router.callback_query(CategoryEdit.filter())
async def rename_category(cb: CallbackQuery, callback_data: CategoryEdit, state: FSMContext, lang: str,
                          session: AsyncSession) -> None:
    category = await CatalogRepo(session).category(callback_data.category_id)
    if category is None:
        await cb.answer(t(lang, "stale_button"), show_alert=True)
        return
    await state.clear()
    await state.update_data(category_id=category.id)
    await state.set_state(CategoryForm.name_en)
    await cb.answer()
    await cb.message.answer(t(lang, "category_rename_en", name=escape(category.name(lang))))


def _name(raw: str, renaming: bool) -> tuple[str | None, bool]:
    """(new name or None to keep the old one, whether the input was acceptable)."""
    if raw.strip() == "-":
        return None, renaming
    value = clean_text(raw, 64)
    return value, value is not None


@router.message(CategoryForm.name_en, TEXT)
async def got_name_en(message: Message, state: FSMContext, lang: str) -> None:
    data = await state.get_data()
    renaming = "category_id" in data
    value, ok = _name(message.text, renaming)
    if not ok:
        await message.answer(t(lang, "invalid_text"))
        return
    await state.update_data(name_en=value)
    await state.set_state(CategoryForm.name_ru)
    await message.answer(t(lang, "category_rename_ru" if renaming else "category_ask_ru"))


@router.message(CategoryForm.name_ru, TEXT)
async def got_name_ru(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    data = await state.get_data()
    category_id = data.get("category_id")
    name_ru, ok = _name(message.text, category_id is not None)
    if not ok:
        await message.answer(t(lang, "invalid_text"))
        return
    await state.clear()
    repo = CatalogRepo(session)
    if category_id is None:
        sort = max((c.sort for c in await repo.categories()), default=-1) + 1
        await repo.add_category(data["name_en"], name_ru, sort)
    else:
        category = await repo.category(category_id)
        if category is None:
            await message.answer(t(lang, "stale_button"))
            return
        category.name_en = data["name_en"] or category.name_en
        category.name_ru = name_ru or category.name_ru
    await message.answer(t(lang, "category_saved"))
    await _render(message, lang, session)


@router.callback_query(CategoryDelete.filter())
async def delete_category_button(cb: CallbackQuery, callback_data: CategoryDelete, lang: str,
                                 session: AsyncSession) -> None:
    repo = CatalogRepo(session)
    category = await repo.category(callback_data.category_id)
    if category is None:
        await cb.answer(t(lang, "stale_button"), show_alert=True)
        return
    count = await repo.count_in_category(category.id)
    if count:
        await cb.answer(t(lang, "category_not_empty", count=count), show_alert=True)
        return
    if not callback_data.confirmed:
        await show(cb, t(lang, "category_delete_confirm", name=escape(category.name(lang))),
                   akb.delete_category_confirm(lang, category.id))
        return
    await delete_category(session, category.id)
    await cb.answer(t(lang, "category_deleted"))
    await _render(cb, lang, session)
