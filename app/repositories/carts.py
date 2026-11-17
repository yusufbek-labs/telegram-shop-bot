from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CartItem


class CartRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def items(self, user_id: int) -> list[CartItem]:
        res = await self.session.scalars(select(CartItem).where(CartItem.user_id == user_id).order_by(CartItem.id))
        return list(res.unique())

    async def get(self, user_id: int, product_id: int) -> CartItem | None:
        res = await self.session.scalars(
            select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
        )
        return res.unique().one_or_none()

    async def set_quantity(self, user_id: int, product_id: int, quantity: int) -> None:
        item = await self.get(user_id, product_id)
        if item is None:
            self.session.add(CartItem(user_id=user_id, product_id=product_id, quantity=quantity))
        else:
            item.quantity = quantity
        await self.session.flush()

    async def remove(self, user_id: int, product_id: int) -> None:
        await self.session.execute(
            delete(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
        )

    async def clear(self, user_id: int) -> None:
        await self.session.execute(delete(CartItem).where(CartItem.user_id == user_id))
