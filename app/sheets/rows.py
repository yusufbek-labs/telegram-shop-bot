"""Conversion between database objects and sheet rows."""
from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo

from app.db.models import Category, Order, Product
from app.formatting import payment_label


def order_row(order: Order, tz: ZoneInfo) -> list:
    created = order.created_at.replace(tzinfo=timezone.utc).astimezone(tz)
    items = "; ".join(f"{i.name} x {i.quantity}" for i in order.items)
    return [
        order.id,
        created.strftime("%Y-%m-%d %H:%M"),
        order.customer_name,
        order.phone,
        order.address,
        items,
        order.total_cents / 100,
        payment_label("en", order.payment_method).split(" ", 1)[-1],  # drop the emoji
        "yes" if order.receipt_file_id else "no",
        order.status,
    ]


def menu_row(product: Product, category: Category | None) -> list:
    return [
        category.name_en if category else "",
        product.name,
        product.description or "",
        product.price_cents / 100,
        product.image_url or "",
        "yes" if product.is_active else "no",
    ]
