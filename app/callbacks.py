"""Typed callback data (aiogram CallbackData factories)."""
from aiogram.filters.callback_data import CallbackData


class Menu(CallbackData, prefix="m"):
    action: str  # home | catalog | cart | search | orders | language | help


class Cat(CallbackData, prefix="c"):
    id: int


class AddToCart(CallbackData, prefix="a"):
    product_id: int


class CartAct(CallbackData, prefix="k"):
    action: str  # inc | dec | del | clear | checkout
    product_id: int = 0


class Pay(CallbackData, prefix="pay"):
    method: str


class Confirm(CallbackData, prefix="cf"):
    ctx: str  # checkout | product | broadcast
    ok: bool


class Lang(CallbackData, prefix="l"):
    code: str


class OrderStatusCb(CallbackData, prefix="os"):
    order_id: int
    status: str


class OrderOpen(CallbackData, prefix="oo"):
    order_id: int


class OrdersFilter(CallbackData, prefix="of"):
    status: str  # "all" or a status


class ProductToggle(CallbackData, prefix="pt"):
    product_id: int


class ProductEdit(CallbackData, prefix="pe"):
    product_id: int


class PickCategory(CallbackData, prefix="pc"):
    category_id: int


class EditField(CallbackData, prefix="ef"):
    field: str  # name | price | description | image


class OrderReceipt(CallbackData, prefix="or"):
    order_id: int


class AdminNav(CallbackData, prefix="an"):
    section: str  # products | categories


class ProductDelete(CallbackData, prefix="pd"):
    product_id: int
    confirmed: bool = False


class CategoryNew(CallbackData, prefix="cn"):
    pass


class CategoryEdit(CallbackData, prefix="ce"):
    category_id: int


class CategoryDelete(CallbackData, prefix="cd"):
    category_id: int
    confirmed: bool = False
