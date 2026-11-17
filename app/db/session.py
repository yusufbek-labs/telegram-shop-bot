"""Async engine and session factory."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base


def create_engine_and_sessionmaker(db_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    if db_url.startswith("sqlite") and ":memory:" not in db_url:
        path = db_url.split("///", 1)[-1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(db_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create tables if they do not exist (no migrations needed at this scope)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
