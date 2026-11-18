"""Admin product management: list/toggle, /add_product and /edit_product FSMs."""
from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.callbacks import AdminNav, Confirm, EditField, PickCategory, ProductDelete, ProductEdit, ProductToggle
from app.config import Settings
from app.formatting import product_card
from app.handlers.common import IsAdmin, show
from app.i18n import t
from app.keyboards import admin as akb
from app.keyboards import customer as ckb
from app.repositories import CatalogRepo
from app.services.catalog import delete_product
from app.services.money import format_money, parse_price
from app.services.validation import clean_text, clean_url
from app.states import AddProduct, EditProduct

router = Router(name="admin_products")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

TEXT = F.text & ~F.text.startswith("/")


async def _render_products(event, lang: str, session: AsyncSession, settings: Settings) -> None:
    products = await CatalogRepo(session).products(only_active=False)
    if not products:
        await show(event, t(lang, "no_products"))
        return
    await show(event, t(lang, "admin_products_title"), akb.products_admin(lang, products, settings.currency_symbol))


@router.message(Command("products"))
async def cmd_products(message: Message, state: FSMContext, lang: str, session: AsyncSession, settings: Settings) -> None:
    await state.clear()
    await _render_products(message, lang, session, settings)


@router.callback_query(ProductToggle.filter())
async def toggle_product(cb: CallbackQuery, callback_data: ProductToggle, lang: str, session: AsyncSession,
                         settings: Settings) -> None:
    product = await CatalogRepo(session).product(callback_data.product_id)
    if product is None:
        await cb.answer(t(lang, "stale_button"), show_alert=True)
        return
    product.is_active = not product.is_active
    state_text = t(lang, "state_on" if product.is_active else "state_off")
    await cb.answer(t(lang, "product_toggled", name=product.name, state=state_text))
    await _render_products(cb, lang, session, settings)


@router.callback_query(AdminNav.filter(F.section == "products"))
async def products_nav(cb: CallbackQuery, lang: str, session: AsyncSession, settings: Settings) -> None:
    await _render_products(cb, lang, session, settings)


@router.callback_query(ProductDelete.filter())
async def delete_product_button(cb: CallbackQuery, callback_data: ProductDelete, lang: str,
                                session: AsyncSession, settings: Settings) -> None:
    product = await CatalogRepo(session).product(callback_data.product_id)
    if product is None:
        await cb.answer(t(lang, "stale_button"), show_alert=True)
        return
    if not callback_data.confirmed:
        await show(cb, t(lang, "product_delete_confirm", name=escape(product.name)),
                   akb.delete_product_confirm(lang, product.id))
        return
    await delete_product(session, product.id)
    await cb.answer(t(lang, "product_deleted"))
    await _render_products(cb, lang, session, settings)


@router.message(Command("add_product"))
async def cmd_add_product(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    await state.clear()
    cats = await CatalogRepo(session).categories()
    if not cats:
        await message.answer(t(lang, "no_categories"))
        return
    await state.set_state(AddProduct.category)
    await message.answer(t(lang, "add_choose_category"), reply_markup=akb.category_pick(lang, cats))


@router.callback_query(AddProduct.category, PickCategory.filter())
async def add_category(cb: CallbackQuery, callback_data: PickCategory, state: FSMContext, lang: str) -> None:
    await state.update_data(category_id=callback_data.category_id)
    await state.set_state(AddProduct.name)
    await cb.answer()
    await cb.message.answer(t(lang, "add_name"))


@router.message(AddProduct.name, TEXT)
async def add_name(message: Message, state: FSMContext, lang: str) -> None:
    name = clean_text(message.text, 120)
    if name is None:
        await message.answer(t(lang, "invalid_text"))
        return
    await state.update_data(name=name)
    await state.set_state(AddProduct.price)
    await message.answer(t(lang, "add_price"))


@router.message(AddProduct.price, TEXT)
async def add_price(message: Message, state: FSMContext, lang: str) -> None:
    cents = parse_price(message.text)
    if cents is None:
        await message.answer(t(lang, "invalid_price"))
        return
    await state.update_data(price_cents=cents)
    await state.set_state(AddProduct.description)
    await message.answer(t(lang, "add_description"))


@router.message(AddProduct.description, TEXT)
async def add_description(message: Message, state: FSMContext, lang: str) -> None:
    text = clean_text(message.text, 1000)
    if text is None:
        await message.answer(t(lang, "invalid_text"))
        return
    await state.update_data(description=text)
    await state.set_state(AddProduct.image)
    await message.answer(t(lang, "add_image"))


@router.message(AddProduct.image, TEXT)
async def add_image(message: Message, state: FSMContext, lang: str, settings: Settings) -> None:
    raw = message.text.strip()
    url = None
    if raw != "-":
        url = clean_url(raw)
        if url is None:
            await message.answer(t(lang, "invalid_url"))
            return
    await _preview(message, state, lang, settings, url)


@router.message(AddProduct.image, F.photo)
async def add_image_photo(message: Message, state: FSMContext, lang: str, settings: Settings) -> None:
    # Telegram accepts a stored file_id wherever a photo URL is accepted, so it goes in image_url too.
    await _preview(message, state, lang, settings, message.photo[-1].file_id)


async def _preview(message: Message, state: FSMContext, lang: str, settings: Settings, image: str | None) -> None:
    await state.update_data(image_url=image)
    data = await state.get_data()
    if image is None:
        image_line = ""
    else:
        image_line = "\n" + (escape(image) if image.startswith("http") else t(lang, "image_photo"))
    card = (
        f"<b>{escape(data['name'])}</b>\n{escape(data['description'])}\n\n"
        f"{format_money(data['price_cents'], settings.currency_symbol)}{image_line}"
    )
    await state.set_state(AddProduct.confirm)
    await message.answer(t(lang, "add_confirm", card=card), reply_markup=ckb.confirm(lang, "product"))


@router.callback_query(AddProduct.confirm, Confirm.filter(F.ctx == "product"))
async def add_confirm(cb: CallbackQuery, callback_data: Confirm, state: FSMContext, lang: str,
                      session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    if not callback_data.ok:
        await show(cb, t(lang, "cancelled"))
        return
    product = await CatalogRepo(session).add_product(
        category_id=data["category_id"], name=data["name"], description=data["description"],
        price_cents=data["price_cents"], image_url=data.get("image_url"), is_active=True,
    )
    await show(cb, t(lang, "product_saved", id=product.id))


@router.message(Command("edit_product"))
async def cmd_edit_product(message: Message, state: FSMContext, lang: str, session: AsyncSession) -> None:
    await state.clear()
    products = await CatalogRepo(session).products(only_active=False)
    if not products:
        await message.answer(t(lang, "no_products"))
        return
    await message.answer(t(lang, "edit_choose_product"), reply_markup=akb.products_to_edit(lang, products))


@router.callback_query(ProductEdit.filter())
async def edit_pick_product(cb: CallbackQuery, callback_data: ProductEdit, state: FSMContext, lang: str,
                            session: AsyncSession) -> None:
    product = await CatalogRepo(session).product(callback_data.product_id)
    if product is None:
        await cb.answer(t(lang, "stale_button"), show_alert=True)
        return
    await state.set_state(EditProduct.field)
    await state.update_data(product_id=product.id)
    await cb.answer()
    await cb.message.answer(t(lang, "edit_choose_field", name=escape(product.name)), reply_markup=akb.edit_fields(lang))


@router.callback_query(EditProduct.field, EditField.filter())
async def edit_pick_field(cb: CallbackQuery, callback_data: EditField, state: FSMContext, lang: str,
                          session: AsyncSession) -> None:
    await state.update_data(field=callback_data.field)
    await state.set_state(EditProduct.value)
    await cb.answer()
    if callback_data.field == "category":
        cats = await CatalogRepo(session).categories()
        await cb.message.answer(t(lang, "edit_ask_category"), reply_markup=akb.category_pick(lang, cats))
        return
    await cb.message.answer(t(lang, "edit_ask_value", field=t(lang, f"field_{callback_data.field}")))


@router.callback_query(EditProduct.value, PickCategory.filter())
async def edit_category(cb: CallbackQuery, callback_data: PickCategory, state: FSMContext, lang: str,
                        session: AsyncSession, settings: Settings) -> None:
    data = await state.get_data()
    repo = CatalogRepo(session)
    product = await repo.product(data["product_id"])
    category = await repo.category(callback_data.category_id)
    await state.clear()
    if product is None or category is None:
        await cb.answer(t(lang, "stale_button"), show_alert=True)
        return
    product.category_id = category.id
    await cb.answer()
    await cb.message.answer(
        t(lang, "product_updated") + "\n\n" + product_card(lang, product, settings.currency_symbol)
    )


@router.message(EditProduct.value, TEXT)
async def edit_value(message: Message, state: FSMContext, lang: str, session: AsyncSession,
                     settings: Settings) -> None:
    data = await state.get_data()
    field, raw = data["field"], message.text
    changes: dict
    if field == "category":  # chosen with the buttons, not typed
        await message.answer(t(lang, "edit_ask_category"))
        return
    if field == "name":
        value = clean_text(raw, 120)
        changes, error = {"name": value}, (value is None and "invalid_text")
    elif field == "description":
        value = clean_text(raw, 1000)
        changes, error = {"description": value}, (value is None and "invalid_text")
    elif field == "price":
        value = parse_price(raw)
        changes, error = {"price_cents": value}, (value is None and "invalid_price")
    else:  # image
        if raw.strip() == "-":
            changes, error = {"image_url": None}, False
        else:
            value = clean_url(raw)
            changes, error = {"image_url": value}, (value is None and "invalid_url")
    if error:
        await message.answer(t(lang, error))
        return
    await _apply_changes(message, state, lang, session, settings, changes)


@router.message(EditProduct.value, F.photo)
async def edit_value_photo(message: Message, state: FSMContext, lang: str, session: AsyncSession,
                           settings: Settings) -> None:
    data = await state.get_data()
    if data["field"] != "image":
        await message.answer(t(lang, "text_expected"))
        return
    await _apply_changes(message, state, lang, session, settings, {"image_url": message.photo[-1].file_id})


async def _apply_changes(message: Message, state: FSMContext, lang: str, session: AsyncSession,
                         settings: Settings, changes: dict) -> None:
    data = await state.get_data()
    product = await CatalogRepo(session).product(data["product_id"])
    await state.clear()
    if product is None:
        await message.answer(t(lang, "stale_button"))
        return
    for key, val in changes.items():
        setattr(product, key, val)
    await message.answer(
        t(lang, "product_updated") + "\n\n" + product_card(lang, product, settings.currency_symbol)
    )
