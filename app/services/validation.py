"""Input validation for checkout and admin forms."""
from __future__ import annotations

import re
from urllib.parse import urlparse

_PHONE_STRIP = re.compile(r"[\s\-().]")
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def clean_name(text: str) -> str | None:
    text = " ".join(text.split())
    return text if 2 <= len(text) <= 60 else None


def clean_phone(text: str) -> str | None:
    compact = _PHONE_STRIP.sub("", text)
    return compact if _PHONE_RE.match(compact) else None


def clean_address(text: str) -> str | None:
    text = " ".join(text.split())
    return text if 5 <= len(text) <= 200 else None


def clean_text(text: str, max_len: int = 200) -> str | None:
    text = text.strip()
    return text if 1 <= len(text) <= max_len else None


def clean_url(text: str) -> str | None:
    text = text.strip()
    parsed = urlparse(text)
    if parsed.scheme in ("http", "https") and parsed.netloc and len(text) <= 500:
        return text
    return None
