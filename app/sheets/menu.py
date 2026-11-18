"""The Menu tab as the source of truth for categories and products."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import CatalogRepo
from app.services.catalog import normalize
from app.services.money import parse_price
from app.sheets.rows import menu_row

log = logging.getLogger(__name__)

YES = {"yes", "y", "true", "1", "да"}
NO = {"no", "n", "false", "0", "нет"}
NAME_MAX, CATEGORY_MAX = 120, 64


@dataclass(frozen=True)
class MenuRow:
    category: str
    name: str
    description: str
    price_cents: int
    photo: str
    available: bool


@dataclass
class MenuReport:
    created: int = 0
    updated: int = 0
    hidden: int = 0
    skipped: int = 0
    rows: int = 0
    problems: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (f"{self.rows} rows: {self.created} added, {self.updated} updated, "
                f"{self.hidden} hidden, {self.skipped} skipped")


def _cell(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""


def parse_menu(rows: list[list[str]]) -> tuple[list[MenuRow], list[str]]:
    """Rows after the header -> valid menu rows plus one message per row that had to be skipped."""
    parsed: list[MenuRow] = []
    problems: list[str] = []
    seen: set[str] = set()
    for number, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        category, name, description = _cell(row, 0), _cell(row, 1), _cell(row, 2)
        price = parse_price(_cell(row, 3))
        flag = _cell(row, 5).casefold()
        photo = _cell(row, 4)
        error = None
        if not category or len(category) > CATEGORY_MAX:
            error = "category is empty or longer than 64 characters"
        elif not name or len(name) > NAME_MAX:
            error = "name is empty or longer than 120 characters"
        elif price is None:
            error = f"bad price {_cell(row, 3)!r}"
        elif flag and flag not in YES | NO:
            error = f"available must be yes or no, got {_cell(row, 5)!r}"
        elif normalize(name) in seen:
            error = f"duplicate product name {name!r}"
        if error:
            problems.append(f"Menu row {number}: {error}")
            continue
        seen.add(normalize(name))
        parsed.append(MenuRow(category, name, description, price, photo, flag not in NO))
    return parsed, problems


async def apply_menu(session: AsyncSession, rows: list[list[str]]) -> MenuReport:
    """Make the database match the sheet. Never deletes: products missing from the sheet are hidden."""
    parsed, problems = parse_menu(rows)
    report = MenuReport(skipped=len(problems), problems=problems, rows=len(parsed) + len(problems))
    for problem in problems:
        log.warning("skipped %s", problem)
    if not parsed:
        if rows[1:] and any(any(c.strip() for c in r) for r in rows[1:]):
            log.warning("Menu tab has no valid rows, catalog left unchanged")
        return report

    repo = CatalogRepo(session)
    categories = {}
    for cat in await repo.categories():
        categories.setdefault(normalize(cat.name_en), cat)
        categories.setdefault(normalize(cat.name_ru), cat)
    next_sort = max((c.sort for c in categories.values()), default=-1) + 1
    products = {}
    for product in await repo.products(only_active=False):
        products.setdefault(normalize(product.name), product)

    listed: set[int] = set()
    for row in parsed:
        cat = categories.get(normalize(row.category))
        if cat is None:
            cat = await repo.add_category(row.category, row.category, next_sort)
            categories[normalize(row.category)] = cat
            next_sort += 1
        product = products.get(normalize(row.name))
        if product is None:
            product = await repo.add_product(
                category_id=cat.id, name=row.name, description=row.description, price_cents=row.price_cents,
                image_url=row.photo or None, is_active=row.available,
            )
            report.created += 1
        else:
            changes = {
                "category_id": cat.id, "name": row.name, "description": row.description,
                "price_cents": row.price_cents, "is_active": row.available,
            }
            if row.photo:  # an empty cell keeps the photo, so one uploaded in the bot is not wiped
                changes["image_url"] = row.photo
            if any(getattr(product, key) != value for key, value in changes.items()):
                for key, value in changes.items():
                    setattr(product, key, value)
                report.updated += 1
        listed.add(product.id)

    for product in products.values():
        if product.id not in listed and product.is_active:
            product.is_active = False
            report.hidden += 1
    await session.flush()
    return report


async def export_menu(session: AsyncSession) -> list[list]:
    """The current catalog as Menu rows, to start a new tab from."""
    repo = CatalogRepo(session)
    categories = {c.id: c for c in await repo.categories()}
    return [menu_row(p, categories.get(p.category_id)) for p in await repo.products(only_active=False)]
