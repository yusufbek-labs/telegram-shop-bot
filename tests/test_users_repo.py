import asyncio

from sqlalchemy import func, select

from app.db.models import User
from app.repositories.users import UserRepo


async def _first_contact(sessionmaker, user_id: int) -> bool:
    async with sessionmaker() as session:
        _, created = await UserRepo(session).upsert(user_id, "buyer", "Buyer", "en")
        await session.commit()
        return created


async def test_parallel_first_messages_create_one_user(sessionmaker):
    results = await asyncio.gather(*(_first_contact(sessionmaker, 1001) for _ in range(3)))

    assert sorted(results) == [False, False, True]
    async with sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(User).where(User.id == 1001))
    assert count == 1


async def test_upsert_refreshes_profile_but_keeps_language(sessionmaker):
    async with sessionmaker() as session:
        await UserRepo(session).upsert(1002, "old", "Old Name", "en")
        await session.commit()

    async with sessionmaker() as session:
        user, created = await UserRepo(session).upsert(1002, "new", "New Name", "ru")
        await session.commit()

    assert created is False
    assert (user.username, user.full_name, user.language) == ("new", "New Name", "en")
