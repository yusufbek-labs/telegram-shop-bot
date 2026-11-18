"""Async engine and session factory."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base


def create_engine_and_sessionmaker(db_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    if db_url.startswith("sqlite") and ":memory:" not in db_url:
        path = db_url.split("///", 1)[-1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(db_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _add_missing_columns(conn: Connection) -> None:
    """Upgrade a database made by an older version: add columns the models have and the tables lack.

    Only nullable columns can be added this way; anything bigger needs a real migration tool.
    """
    inspector = inspect(conn)
    quote = conn.dialect.identifier_preparer.quote
    for table in Base.metadata.sorted_tables:
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            if not column.nullable:
                raise RuntimeError(f"cannot add required column {table.name}.{column.name} to an existing table")
            conn.exec_driver_sql(
                f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(column.name)} {column.type.compile(conn.dialect)}"
            )


async def init_db(engine: AsyncEngine) -> None:
    """Create missing tables and add missing nullable columns (no migration tool at this scope)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
