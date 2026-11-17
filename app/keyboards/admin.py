from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import (
    EditField,
    Menu,
    OrderOpen,
    OrdersFilter,
    OrderStatusCb,
    PickCategory,
    ProductEdit,
    ProductToggle,
)
from app.db.models import Category, Order, Product
from app.formatting import status_label
from app.i18n import t
from app.services.money import format_money
from app.services.orders import STATUSES, allowed_next


def order_actions(lang: str, order: Order) -> InlineKeyboardMarkup:
    """Only the transitions the state machine allows from the current status."""
    b = InlineKeyboardBuilder()
    for nxt in allowed_next(order.status):
        b.button(text=status_label(lang, nxt), callback_data=OrderStatusCb(order_id=order.id, status=nxt))
    b.adjust(2, repeat=True)
    return b.as_markup()


def orders_filter(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "filter_all"), callback_data=OrdersFilter(status="all"))
    for s in STATUSES:
        b.button(text=status_label(lang, s), callback_data=OrdersFilter(status=s))
    b.adjust(2, repeat=True)
    return b.as_markup()


def orders_list(lang: str, orders: list[Order], symbol: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in orders:
        label = t(lang, "order_line", id=o.id, status=status_label(lang, o.status), total=format_money(o.total_cents, symbol))
        b.button(text=label, callback_data=OrderOpen(order_id=o.id))
    b.button(text=t(lang, "btn_back"), callback_data=OrdersFilter(status="menu"))
    b.adjust(1, repeat=True)
    return b.as_markup()


def products_admin(lang: str, products: list[Product], symbol: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        mark = "🟢" if p.is_active else "🔴"
        b.button(text=f"{mark} #{p.id} {p.name[:20]} · {format_money(p.price_cents, symbol)}", callback_data=ProductToggle(product_id=p.id))
        b.button(text=t(lang, "btn_edit"), callback_data=ProductEdit(product_id=p.id))
    b.adjust(2, repeat=True)
    return b.as_markup()


def products_to_edit(lang: str, products: list[Product]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in products:
        b.button(text=f"#{p.id} {p.name[:30]}", callback_data=ProductEdit(product_id=p.id))
    b.adjust(1, repeat=True)
    return b.as_markup()


def category_pick(lang: str, cats: list[Category]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in cats:
        b.button(text=c.name(lang), callback_data=PickCategory(category_id=c.id))
    b.adjust(2, repeat=True)
    return b.as_markup()


def edit_fields(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for f in ("name", "price", "description", "image"):
        b.button(text=t(lang, f"field_{f}"), callback_data=EditField(field=f))
    b.adjust(2, repeat=True)
    return b.as_markup()
