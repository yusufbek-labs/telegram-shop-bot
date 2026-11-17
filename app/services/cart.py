"""Cart business logic."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import CartRepo, CatalogRepo

MAX_QTY = 99


class ProductUnavailable(Exception):
    pass


@dataclass(frozen=True)
class CartLine:
    product_id: int
    name: str
    unit_price_cents: int
    quantity: int

    @property
    def subtotal_cents(self) -> int:
        return self.unit_price_cents * self.quantity


@dataclass(frozen=True)
class CartView:
    lines: list[CartLine]

    @property
    def total_cents(self) -> int:
        return cart_total(self.lines)

    @property
    def is_empty(self) -> bool:
        return not self.lines


def cart_total(lines: Iterable[CartLine]) -> int:
    return sum(line.subtotal_cents for line in lines)


def clamp_quantity(quantity: int) -> int:
    return max(0, min(MAX_QTY, quantity))


class CartService:
    def __init__(self, session: AsyncSession):
        self.carts = CartRepo(session)
        self.catalog = CatalogRepo(session)

    async def view(self, user_id: int) -> CartView:
        items = await self.carts.items(user_id)
        return CartView(
            [CartLine(i.product_id, i.product.name, i.product.price_cents, i.quantity) for i in items]
        )

    async def add(self, user_id: int, product_id: int, quantity: int = 1):
        product = await self.catalog.product(product_id)
        if product is None or not product.is_active:
            raise ProductUnavailable(product_id)
        existing = await self.carts.get(user_id, product_id)
        new_qty = clamp_quantity((existing.quantity if existing else 0) + quantity)
        await self.carts.set_quantity(user_id, product_id, new_qty)
        return product

    async def change_quantity(self, user_id: int, product_id: int, delta: int) -> None:
        """Add or subtract; dropping to zero removes the line."""
        existing = await self.carts.get(user_id, product_id)
        if existing is None:
            return
        new_qty = clamp_quantity(existing.quantity + delta)
        if new_qty == 0:
            await self.carts.remove(user_id, product_id)
        else:
            await self.carts.set_quantity(user_id, product_id, new_qty)

    async def remove(self, user_id: int, product_id: int) -> None:
        await self.carts.remove(user_id, product_id)

    async def clear(self, user_id: int) -> None:
        await self.carts.clear(user_id)
