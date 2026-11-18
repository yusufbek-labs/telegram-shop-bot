"""Entry point: `python -m app`."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app import demo
from app.bot import build_dispatcher, set_commands
from app.config import get_settings
from app.db.session import create_engine_and_sessionmaker, init_db
from app.sheets import create_sheets
from scripts.seed import seed

log = logging.getLogger("app")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


async def run() -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    if not settings.bot_token:
        print("BOT_TOKEN is not set. Copy .env.example to .env and paste the token from @BotFather.")
        return 1
    if not settings.admin_ids:
        log.warning("ADMIN_IDS is empty: nobody can use the admin commands")

    engine, sessionmaker = create_engine_and_sessionmaker(settings.db_url)
    await init_db(engine)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    if settings.demo_mode:
        log.info("demo mode is on: test orders are limited and deleted after %s days", demo.KEEP_DAYS)
        await seed(sessionmaker, demo=True)  # only when the catalog is empty
    sheets = create_sheets(settings)
    dp = build_dispatcher(settings, sessionmaker, sheets)
    sync_task = cleanup_task = None
    try:
        await set_commands(bot, settings)
        me = await bot.get_me()
        log.info("started as @%s, admins=%s", me.username, settings.admin_ids)
        if sheets is not None:
            sync_task = asyncio.create_task(sheets.run_forever(bot, sessionmaker))
        if settings.demo_mode:
            cleanup_task = asyncio.create_task(demo.run_cleanup(sessionmaker))
        await dp.start_polling(bot)
    finally:
        for task in (sync_task, cleanup_task):
            if task is not None:
                task.cancel()
        demo.cancel_pending()
        if sheets is not None:
            await sheets.drain(timeout=15)
        await bot.session.close()
        await engine.dispose()
    return 0


def main() -> None:
    try:
        sys.exit(asyncio.run(run()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
