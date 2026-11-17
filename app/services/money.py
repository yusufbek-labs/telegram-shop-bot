"""Money helpers. Prices are integer cents everywhere to avoid float errors."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

MAX_PRICE_CENTS = 100_000_000  # 1,000,000.00


def format_money(cents: int, symbol: str = "$") -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{symbol}{cents // 100}.{cents % 100:02d}"


def parse_price(text: str) -> int | None:
    """Parse '12.5' / '12,50' into cents. Returns None when invalid, zero or absurd."""
    cleaned = text.strip().replace(",", ".").replace(" ", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not value.is_finite() or value <= 0:
        return None
    cents = int((value * 100).to_integral_value())
    if cents <= 0 or cents > MAX_PRICE_CENTS:
        return None
    return cents
