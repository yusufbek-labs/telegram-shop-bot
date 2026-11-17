"""Who may do what. Admin ids come from configuration only."""
from __future__ import annotations

from collections.abc import Iterable


class PermissionDenied(Exception):
    pass


def is_admin(user_id: int | None, admin_ids: Iterable[int]) -> bool:
    return user_id is not None and user_id in set(admin_ids)


def require_admin(user_id: int | None, admin_ids: Iterable[int]) -> None:
    if not is_admin(user_id, admin_ids):
        raise PermissionDenied(f"user {user_id} is not an admin")
