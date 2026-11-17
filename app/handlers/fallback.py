"""Last-resort handlers: unknown commands, free text, stale buttons."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.handlers.common import ADMIN_COMMANDS
from app.i18n import t
from app.keyboards import customer as kb

router = Router(name="fallback")


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message, lang: str, settings: Settings) -> None:
    command = message.text.split()[0].lstrip("/").split("@")[0].lower()
    if command in ADMIN_COMMANDS:
        await message.answer(t(lang, "no_permission"))
    else:
        await message.answer(t(lang, "unknown_command"), reply_markup=kb.main_menu(lang))


@router.message()
async def unknown_input(message: Message, lang: str) -> None:
    await message.answer(t(lang, "unknown_input"), reply_markup=kb.main_menu(lang))


@router.callback_query()
async def stale_callback(cb: CallbackQuery, lang: str) -> None:
    await cb.answer(t(lang, "stale_button"), show_alert=True)
