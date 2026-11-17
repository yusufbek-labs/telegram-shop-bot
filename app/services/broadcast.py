"""Broadcast with a rate limiter that keeps well under Telegram's ~30 msg/s limit."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter

log = logging.getLogger(__name__)

TELEGRAM_MAX_RATE = 30.0


class RateLimiter:
    """Spaces calls at least 1/rate seconds apart. Clock and sleep are injectable for tests."""

    def __init__(
        self,
        rate: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        if rate <= 0 or rate > TELEGRAM_MAX_RATE:
            raise ValueError(f"rate must be in (0, {TELEGRAM_MAX_RATE}] messages per second")
        self.interval = 1.0 / rate
        self._clock = clock
        self._sleep = sleep
        self._next_slot = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            start = max(now, self._next_slot)
            wait = start - now
            if wait > 0:
                await self._sleep(wait)
            self._next_slot = start + self.interval


@dataclass
class BroadcastResult:
    sent: int = 0
    blocked: int = 0
    failed: int = 0


async def broadcast(
    bot: Bot,
    user_ids: Iterable[int],
    text: str,
    limiter: RateLimiter,
    on_blocked: Callable[[int], Awaitable[None]] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    max_retries: int = 3,
) -> BroadcastResult:
    """Send `text` to every user. Honours Telegram's retry_after and flags users who blocked the bot."""
    result = BroadcastResult()
    for uid in user_ids:
        for attempt in range(max_retries + 1):
            await limiter.acquire()
            try:
                await bot.send_message(uid, text)
                result.sent += 1
            except TelegramRetryAfter as exc:
                log.warning("flood control: sleeping %ss", exc.retry_after)
                await sleep(exc.retry_after)
                if attempt == max_retries:
                    result.failed += 1
                continue
            except TelegramForbiddenError:
                result.blocked += 1
                if on_blocked:
                    await on_blocked(uid)
            except TelegramAPIError as exc:
                log.warning("broadcast to %s failed: %s", uid, exc)
                result.failed += 1
            break
    return result
