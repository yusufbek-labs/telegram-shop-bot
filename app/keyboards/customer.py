from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import AddToCart, Cat, CartAct, Confirm, Lang, Menu, Pay
from app.db.models import Category
from app.i18n import t
from app.services.cart import CartLine
from app.services.orders import PAYMENT_METHODS


def main_menu(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_catalog"), callback_data=Menu(action="catalog"))
    b.button(text=t(lang, "btn_cart"), callback_data=Menu(action="cart"))
    b.button(text=t(lang, "btn_search"), callback_data=Menu(action="search"))
    b.button(text=t(lang, "btn_orders"), callback_data=Menu(action="orders"))
    b.button(text=t(lang, "btn_language"), callback_data=Menu(action="language"))
    b.button(text=t(lang, "btn_help"), callback_data=Menu(action="help"))
    b.adjust(2, repeat=True)
    return b.as_markup()


def back_to_menu(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_menu"), callback_data=Menu(action="home"))
    return b.as_markup()


def categories(lang: str, cats: list[Category]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=c.name(lang), callback_data=Cat(id=c.id))
    b.adjust(2, repeat=True)
    b.row(*back_to_menu(lang).inline_keyboard[0])
    return b.as_markup()


def product_card_kb(lang: str, product_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_add"), callback_data=AddToCart(product_id=product_id))
    return b.as_markup()


def after_products(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_back"), callback_data=Menu(action="catalog"))
    b.button(text=t(lang, "btn_cart"), callback_data=Menu(action="cart"))
    b.adjust(2, repeat=True)
    return b.as_markup()


def after_search(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_search_again"), callback_data=Menu(action="search"))
    b.button(text=t(lang, "btn_catalog"), callback_data=Menu(action="catalog"))
    b.button(text=t(lang, "btn_cart"), callback_data=Menu(action="cart"))
    b.adjust(2, 1)
    return b.as_markup()


def cart(lang: str, lines: list[CartLine]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for line in lines:
        pid = line.product_id
        b.button(text="➖", callback_data=CartAct(action="dec", product_id=pid))
        b.button(text=f"{line.name[:14]} · {line.quantity}", callback_data=CartAct(action="noop", product_id=pid))
        b.button(text="➕", callback_data=CartAct(action="inc", product_id=pid))
        b.button(text="✖️", callback_data=CartAct(action="del", product_id=pid))
    if lines:
        b.adjust(4, repeat=True)
    if lines:
        b.row(*_buttons(
            (t(lang, "btn_checkout"), CartAct(action="checkout")),
            (t(lang, "btn_clear"), CartAct(action="clear")),
        ))
    b.row(*back_to_menu(lang).inline_keyboard[0])
    return b.as_markup()


def _buttons(*pairs):
    from aiogram.types import InlineKeyboardButton

    return [InlineKeyboardButton(text=text, callback_data=cb.pack()) for text, cb in pairs]


def phone_request(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn_share_phone"), request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def payment(lang: str, with_transfer: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for method in PAYMENT_METHODS:
        if method == "transfer" and not with_transfer:
            continue
        b.button(text=t(lang, f"payment_{method}"), callback_data=Pay(method=method))
    b.adjust(1, repeat=True)
    return b.as_markup()


def confirm(lang: str, ctx: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_confirm"), callback_data=Confirm(ctx=ctx, ok=True))
    b.button(text=t(lang, "btn_cancel"), callback_data=Confirm(ctx=ctx, ok=False))
    b.adjust(2, repeat=True)
    return b.as_markup()


def languages() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🇬🇧 English", callback_data=Lang(code="en"))
    b.button(text="🇷🇺 Русский", callback_data=Lang(code="ru"))
    b.adjust(2, repeat=True)
    return b.as_markup()
