"""Order / revenue statistics for the admin /stats command."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import OrderRepo


@dataclass(frozen=True)
class Stats:
    today_orders: int
    today_revenue_cents: int
    week_orders: int
    week_revenue_cents: int


def period_starts(now_utc: datetime, tz_name: str = "UTC") -> tuple[datetime, datetime]:
    """Naive-UTC starts of 'today' (local midnight) and of the 7-day window (today + previous 6 days)."""
    tz = ZoneInfo(tz_name)
    local_now = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start = local_midnight.astimezone(timezone.utc).replace(tzinfo=None)
    week_start = (local_midnight - timedelta(days=6)).astimezone(timezone.utc).replace(tzinfo=None)
    return today_start, week_start


class StatsService:
    def __init__(self, session: AsyncSession, tz_name: str = "UTC"):
        self.orders = OrderRepo(session)
        self.tz_name = tz_name

    async def compute(self, now_utc: datetime | None = None) -> Stats:
        now_utc = now_utc or datetime.now(timezone.utc).replace(tzinfo=None)
        today_start, week_start = period_starts(now_utc, self.tz_name)
        t_count, t_rev = await self.orders.totals_since(today_start)
        w_count, w_rev = await self.orders.totals_since(week_start)
        return Stats(t_count, t_rev, w_count, w_rev)
