"""Tiny i18n layer: dictionaries per language plus t() lookup."""
from __future__ import annotations

from app.i18n.en import TEXTS as EN
from app.i18n.ru import TEXTS as RU

LANGS = ("en", "ru")
DEFAULT_LANG = "en"
TEXTS: dict[str, dict[str, str]] = {"en": EN, "ru": RU}


def resolve_lang(language_code: str | None) -> str:
    """Map a Telegram language_code (e.g. 'ru', 'en-US', 'uk') to a supported language."""
    if language_code and language_code.lower().split("-")[0] in ("ru", "uk", "be"):
        return "ru"
    return DEFAULT_LANG


def t(lang: str, key: str, **kwargs) -> str:
    table = TEXTS.get(lang, TEXTS[DEFAULT_LANG])
    text = table[key]  # a missing key is a bug; tests make sure both languages are complete
    return text.format(**kwargs) if kwargs else text
