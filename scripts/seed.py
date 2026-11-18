"""Fill the database with a small fictional catalog.  Usage: python -m scripts.seed [--force] [--demo]

Idempotent: does nothing when products already exist, unless --force is given
(which wipes products and categories first; orders and users are kept).
--demo (or DEMO_MODE=true) gives every product a public placeholder photo.
"""
from __future__ import annotations

import asyncio
import sys
from urllib.parse import quote_plus

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.models import CartItem, Category, Product
from app.db.session import create_engine_and_sessionmaker, init_db
from app.repositories import CatalogRepo

# (name_en, name_ru, [(product name, description, price in cents, image_url)])
CATALOG = [
    ("Tea", "Чай", [
        ("Alpine Green Tea, 100 g", "Light, grassy green tea with a clean finish. Loose leaf.", 1250, None),
        ("Smoked Black Tea, 100 g", "Dark, malty black tea with a gentle campfire note.", 1400, None),
        ("Mint and Lemon Blend, 80 g", "Caffeine-free herbal blend, great iced in summer.", 1100, None),
    ]),
    ("Candles", "Свечи", [
        ("Pine Forest Candle", "Hand-poured soy wax candle, 40 hours burn time.", 1900,
         "https://placehold.co/600x400/png?text=Pine+Forest+Candle"),
        ("Maple Morning Candle", "Warm maple and vanilla scent in a reusable glass jar.", 2100,
         "https://placehold.co/600x400/png?text=Maple+Morning+Candle"),
        ("Travel Tin Candle", "Pocket-size 8-hour candle in a tin, linen scent.", 900, None),
    ]),
    ("Home and Gifts", "Дом и подарки", [
        ("Ceramic Tea Mug", "Stoneware mug, 300 ml, dishwasher safe.", 1600, None),
        ("Linen Tea Towel", "Soft washed linen, 50 x 70 cm.", 1350, None),
        ("Gift Box: Tea and Candle", "One tea of your choice plus a travel candle, wrapped.", 2800, None),
    ]),
]


def placeholder_photo(name: str) -> str:
    return f"https://placehold.co/600x400/png?text={quote_plus(name)}"


async def seed(sessionmaker: async_sessionmaker[AsyncSession], force: bool = False, demo: bool = False) -> int:
    """Insert the demo catalog. Returns the number of products created (0 if skipped).

    demo=True gives every product a public placeholder photo, for the public demo bot.
    """
    async with sessionmaker() as session:
        repo = CatalogRepo(session)
        if await repo.count_products() and not force:
            return 0
        if force:
            await session.execute(delete(CartItem))
            await session.execute(delete(Product))
            await session.execute(delete(Category))
        created = 0
        for sort, (name_en, name_ru, products) in enumerate(CATALOG):
            cat = await repo.add_category(name_en, name_ru, sort)
            for name, description, price, image in products:
                if image is None and demo:
                    image = placeholder_photo(name)
                await repo.add_product(
                    category_id=cat.id, name=name, description=description, price_cents=price, image_url=image
                )
                created += 1
        await session.commit()
        return created


async def _main() -> None:
    settings = get_settings()
    engine, sessionmaker = create_engine_and_sessionmaker(settings.db_url)
    await init_db(engine)
    demo = "--demo" in sys.argv or settings.demo_mode
    created = await seed(sessionmaker, force="--force" in sys.argv, demo=demo)
    await engine.dispose()
    print(f"Seeded {created} products." if created else "Catalog already has products; nothing to do (use --force to reset).")


if __name__ == "__main__":
    asyncio.run(_main())
