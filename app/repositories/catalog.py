from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Product


class CatalogRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def categories(self) -> list[Category]:
        res = await self.session.scalars(select(Category).order_by(Category.sort, Category.id))
        return list(res)

    async def category(self, category_id: int) -> Category | None:
        return await self.session.get(Category, category_id)

    async def products(self, category_id: int | None = None, only_active: bool = True) -> list[Product]:
        stmt = select(Product).order_by(Product.id)
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if only_active:
            stmt = stmt.where(Product.is_active.is_(True))
        return list(await self.session.scalars(stmt))

    async def product(self, product_id: int) -> Product | None:
        return await self.session.get(Product, product_id)

    async def add_product(self, **fields) -> Product:
        product = Product(**fields)
        self.session.add(product)
        await self.session.flush()
        return product

    async def add_category(self, name_en: str, name_ru: str, sort: int = 0) -> Category:
        cat = Category(name_en=name_en, name_ru=name_ru, sort=sort)
        self.session.add(cat)
        await self.session.flush()
        return cat

    async def count_products(self) -> int:
        return len(await self.products(only_active=False))
