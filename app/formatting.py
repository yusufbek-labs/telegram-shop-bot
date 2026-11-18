"""Text rendering helpers shared by handlers (HTML parse mode)."""
from __future__ import annotations

from html import escape

from app.db.models import Order, Product
from app.i18n import t
from app.services.cart import CartLine, CartView
from app.services.money import format_money


def status_label(lang: str, status: str) -> str:
    return t(lang, f"status_{status}")


def payment_label(lang: str, method: str) -> str:
    return t(lang, f"payment_{method}")


def receipt_line(lang: str, attached: bool) -> str:
    return t(lang, "receipt_line") if attached else ""


def lines_text(lang: str, lines: list[CartLine], symbol: str) -> str:
    return "\n".join(
        t(lang, "cart_line", name=escape(line.name), qty=line.quantity, sum=format_money(line.subtotal_cents, symbol))
        for line in lines
    )


def cart_text(lang: str, view: CartView, symbol: str) -> str:
    if view.is_empty:
        return f"{t(lang, 'cart_title')}\n\n{t(lang, 'cart_empty')}"
    return (
        f"{t(lang, 'cart_title')}\n\n{lines_text(lang, view.lines, symbol)}\n\n"
        f"{t(lang, 'cart_total', total=format_money(view.total_cents, symbol))}"
    )


def product_card(lang: str, product: Product, symbol: str) -> str:
    return t(
        lang,
        "product_card",
        name=escape(product.name),
        description=escape(product.description or ""),
        price=format_money(product.price_cents, symbol),
    )


def order_items_text(order: Order, symbol: str) -> str:
    return "\n".join(
        f"- {escape(i.name)} × {i.quantity} = {format_money(i.unit_price_cents * i.quantity, symbol)}"
        for i in order.items
    )


def order_card(lang: str, order: Order, symbol: str) -> str:
    return t(
        lang,
        "admin_order_card",
        id=order.id,
        status=status_label(lang, order.status),
        created=order.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        name=escape(order.customer_name),
        phone=escape(order.phone),
        address=escape(order.address),
        payment=payment_label(lang, order.payment_method),
        receipt=receipt_line(lang, bool(order.receipt_file_id)),
        items=order_items_text(order, symbol),
        total=format_money(order.total_cents, symbol),
    )
