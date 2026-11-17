"""Entry point: `python -m app`."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot import build_dispatcher, set_commands
from app.config import get_settings
from app.db.session import create_engine_and_sessionmaker, init_db

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
    dp = build_dispatcher(settings, sessionmaker)
    try:
        await set_commands(bot, settings)
        me = await bot.get_me()
        log.info("started as @%s, admins=%s", me.username, settings.admin_ids)
        await dp.start_polling(bot)
    finally:
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
