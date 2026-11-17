from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def upsert(self, user_id: int, username: str | None, full_name: str, language: str) -> tuple[User, bool]:
        """Create the user (with the detected language) or refresh profile data."""
        # A single INSERT ... ON CONFLICT instead of "select, then insert": several first
        # messages from the same user are handled concurrently and would race on the insert.
        result = await self.session.execute(
            insert(User)
            .values(id=user_id, username=username, full_name=full_name, language=language)
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        created = result.rowcount == 1
        user = await self.get(user_id)
        if not created:
            user.username = username
            user.full_name = full_name
            user.is_blocked = False
        return user, created

    async def set_language(self, user_id: int, language: str) -> None:
        await self.session.execute(update(User).where(User.id == user_id).values(language=language))

    async def mark_blocked(self, user_id: int) -> None:
        await self.session.execute(update(User).where(User.id == user_id).values(is_blocked=True))

    async def active_ids(self) -> list[int]:
        res = await self.session.scalars(select(User.id).where(User.is_blocked.is_(False)).order_by(User.id))
        return list(res)
