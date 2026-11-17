"""Broadcast rate limiter, stats, validation, money, config, seed."""
from datetime import datetime, timedelta

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage

from app.config import Settings
from app.db.models import Order, User
from app.repositories import CatalogRepo
from app.services.broadcast import RateLimiter, broadcast
from app.services.money import format_money, parse_price
from app.services.stats import StatsService, period_starts
from app.services.validation import clean_address, clean_name, clean_phone, clean_url
from scripts.seed import seed


class FakeClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps: list[float] = []

    def time(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


async def test_rate_limiter_spaces_calls():
    clock = FakeClock()
    limiter = RateLimiter(10, clock=clock.time, sleep=clock.sleep)  # 10/s -> 0.1 s apart
    stamps = []
    for _ in range(6):
        await limiter.acquire()
        stamps.append(clock.now)
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    assert all(g == pytest.approx(0.1) for g in gaps)
    assert stamps[-1] - stamps[0] == pytest.approx(0.5)


async def test_rate_limiter_never_exceeds_telegram_limit():
    clock = FakeClock()
    limiter = RateLimiter(30, clock=clock.time, sleep=clock.sleep)
    start = clock.now
    for _ in range(61):
        await limiter.acquire()
    assert clock.now - start >= 60 / 30 - 1e-9  # 61 sends need at least 2 seconds


@pytest.mark.parametrize("rate", [0, -1, 31, 1000])
def test_rate_limiter_rejects_rates_over_telegram_limit(rate):
    with pytest.raises(ValueError):
        RateLimiter(rate)


class FakeBot:
    def __init__(self, behaviour):
        self.behaviour = behaviour  # uid -> list of outcomes (exception or None)
        self.sent: list[int] = []

    async def send_message(self, uid, text):
        outcomes = self.behaviour.get(uid, [])
        if outcomes:
            outcome = outcomes.pop(0)
            if outcome:
                raise outcome
        self.sent.append(uid)


async def test_broadcast_counts_blocked_and_retries_flood_control():
    method = SendMessage(chat_id=1, text="x")
    bot = FakeBot({
        2: [TelegramForbiddenError(method, "bot was blocked by the user")],
        3: [TelegramRetryAfter(method, "Flood control", 5)],
    })
    clock = FakeClock()
    limiter = RateLimiter(30, clock=clock.time, sleep=clock.sleep)
    blocked: list[int] = []

    async def on_blocked(uid):
        blocked.append(uid)

    result = await broadcast(bot, [1, 2, 3, 4], "hi", limiter, on_blocked=on_blocked, sleep=clock.sleep)
    assert (result.sent, result.blocked, result.failed) == (3, 1, 0)
    assert blocked == [2]
    assert bot.sent == [1, 3, 4]
    assert 5 in clock.sleeps  # honoured Telegram's retry_after


async def test_broadcast_gives_up_after_max_retries():
    method = SendMessage(chat_id=1, text="x")
    bot = FakeBot({1: [TelegramRetryAfter(method, "Flood", 1)] * 10})
    clock = FakeClock()
    limiter = RateLimiter(30, clock=clock.time, sleep=clock.sleep)
    result = await broadcast(bot, [1, 2], "hi", limiter, sleep=clock.sleep, max_retries=2)
    assert (result.sent, result.failed) == (1, 1)


def test_period_starts_respects_timezone():
    now = datetime(2026, 3, 10, 23, 30)  # 23:30 UTC = 00:30 next day in Berlin (UTC+1)
    today, week = period_starts(now, "Europe/Berlin")
    assert today == datetime(2026, 3, 10, 23, 0)
    assert week == today - timedelta(days=6)
    assert period_starts(now, "UTC")[0] == datetime(2026, 3, 10)


async def test_stats_today_week_and_cancelled_excluded(sessionmaker):
    now = datetime(2026, 6, 15, 12, 0)

    def order(days_ago, cents, status="new"):
        return Order(user_id=1, customer_name="x", phone="1", address="a", payment_method="cash",
                     status=status, total_cents=cents, created_at=now - timedelta(days=days_ago, hours=1))

    async with sessionmaker() as s:
        s.add(User(id=1))
        s.add_all([
            order(0, 1000), order(0, 500, "cancelled"), order(3, 2000), order(6, 300), order(8, 9999),
        ])
        await s.flush()
        stats = await StatsService(s).compute(now)
    assert (stats.today_orders, stats.today_revenue_cents) == (1, 1000)
    assert (stats.week_orders, stats.week_revenue_cents) == (3, 3300)  # the 8-day-old order is outside


@pytest.mark.parametrize("cents,text", [(0, "$0.00"), (5, "$0.05"), (1250, "$12.50"), (123456, "$1234.56")])
def test_format_money(cents, text):
    assert format_money(cents) == text


@pytest.mark.parametrize("raw,cents", [("12.5", 1250), ("12,50", 1250), (" 7 ", 700), ("0.99", 99)])
def test_parse_price_ok(raw, cents):
    assert parse_price(raw) == cents


@pytest.mark.parametrize("raw", ["", "abc", "0", "-3", "nan", "inf", "99999999"])
def test_parse_price_rejects(raw):
    assert parse_price(raw) is None


def test_validators():
    assert clean_name("  Ann   Lee ") == "Ann Lee" and clean_name("A") is None
    assert clean_phone("+1 (555) 123-45-67") == "+15551234567" and clean_phone("hello") is None
    assert clean_phone("12345") is None
    assert clean_address("12 Birch St") and clean_address("x") is None
    assert clean_url("https://example.com/a.png") and clean_url("javascript:alert(1)") is None
    assert clean_url("not a url") is None


def test_admin_ids_parsing(monkeypatch):
    assert Settings(_env_file=None, admin_ids="1, 2;3").admin_ids == [1, 2, 3]
    assert Settings(_env_file=None, admin_ids="").admin_ids == []
    monkeypatch.setenv("ADMIN_IDS", "10,20")
    assert Settings(_env_file=None).admin_ids == [10, 20]


async def test_seed_is_idempotent(sessionmaker):
    assert await seed(sessionmaker) == 9
    assert await seed(sessionmaker) == 0
    async with sessionmaker() as s:
        assert await CatalogRepo(s).count_products() == 9
        assert len(await CatalogRepo(s).categories()) == 3
