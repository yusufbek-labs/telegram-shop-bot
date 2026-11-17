from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order


class OrderRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, order: Order) -> Order:
        self.session.add(order)
        await self.session.flush()
        return order

    async def get(self, order_id: int) -> Order | None:
        return await self.session.get(Order, order_id)

    async def list(self, status: str | None = None, user_id: int | None = None, limit: int = 10) -> list[Order]:
        stmt = select(Order).order_by(Order.id.desc()).limit(limit)
        if status:
            stmt = stmt.where(Order.status == status)
        if user_id is not None:
            stmt = stmt.where(Order.user_id == user_id)
        return list(await self.session.scalars(stmt))

    async def totals_since(self, since: datetime) -> tuple[int, int]:
        """(order count, revenue in cents) since a naive-UTC moment; cancelled orders excluded."""
        stmt = select(func.count(Order.id), func.coalesce(func.sum(Order.total_cents), 0)).where(
            Order.created_at >= since, Order.status != "cancelled"
        )
        count, revenue = (await self.session.execute(stmt)).one()
        return int(count), int(revenue)
