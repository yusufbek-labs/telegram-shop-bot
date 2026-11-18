"""Catalog rules: product search and guarded deletes."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product
from app.repositories import CatalogRepo


class CategoryNotEmpty(Exception):
    def __init__(self, count: int):
        super().__init__(count)
        self.count = count


def normalize(text: str) -> str:
    """Lower-case for matching. casefold() handles Cyrillic, which SQLite's lower() does not."""
    return " ".join(text.casefold().replace("ё", "е").split())


async def search_products(session: AsyncSession, query: str) -> list[Product]:
    """In-stock products whose name or category name contains every word of the query.

    Matching happens in Python because the catalog of a small shop fits in memory; with thousands
    of products, keep a normalized name column and filter in SQL instead.
    """
    words = normalize(query).split()
    if not words:
        return []
    repo = CatalogRepo(session)
    category_names = {c.id: f"{c.name_en} {c.name_ru}" for c in await repo.categories()}
    found = []
    for product in await repo.products():
        haystack = normalize(f"{product.name} {category_names.get(product.category_id, '')}")
        if all(word in haystack for word in words):
            found.append(product)
    return found


async def delete_category(session: AsyncSession, category_id: int) -> bool:
    """Delete an empty category. False if it does not exist, CategoryNotEmpty if it has products."""
    repo = CatalogRepo(session)
    category = await repo.category(category_id)
    if category is None:
        return False
    count = await repo.count_in_category(category_id)
    if count:
        raise CategoryNotEmpty(count)
    await repo.delete_category(category)
    return True


async def delete_product(session: AsyncSession, product_id: int) -> bool:
    repo = CatalogRepo(session)
    product = await repo.product(product_id)
    if product is None:
        return False
    await repo.delete_product(product)
    return True
