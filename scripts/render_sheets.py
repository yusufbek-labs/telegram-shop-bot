"""Render docs/screenshots/11-sheet-orders.png and 12-sheet-menu.png from what the in-memory sheet really holds.

Usage: python -m scripts.render_sheets      (needs Microsoft Edge, like scripts/render_demo.py)
A demo checkout runs through the real handlers with SheetsSync attached to a MemorySheet; the owner then
"edits" cells the way they would in Google Sheets and the real sync code applies them. The pages only
draw the resulting tabs as a spreadsheet; the sheet is not a screenshot of Google Sheets.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
from html import escape
from pathlib import Path

from app.config import Settings
from app.db.session import create_engine_and_sessionmaker, init_db
from app.sheets import SheetsSync
from app.sheets.backend import MENU_TAB, ORDERS_TAB, STATUS_COL
from app.sheets.memory import MemorySheet
from scripts.capture_demo import (
    ADMIN_ID, CUSTOMER_ADDRESS, CUSTOMER_ID, CUSTOMER_NAME, CUSTOMER_PHONE, PAYMENT_DETAILS, RECEIPT_FILE_ID, Scenario,
)
from scripts.render_demo import ROOT, SHOTS, edge
from scripts.seed import seed

CSS = """
:root{--ink:#1f2328;--muted:#5f6b76;--line:#d0d7de;--head:#f1f3f4;--bar:#188038}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font:13px/1.35 "Segoe UI",system-ui,sans-serif}
.sheet{width:%(width)spx}
.top{display:flex;align-items:center;gap:12px;padding:10px 14px;border-bottom:1px solid var(--line)}
.logo{width:22px;height:30px;background:var(--bar);border-radius:3px}
.name{font-size:16px;font-weight:600}.sub{color:var(--muted);font-size:12px}
.demo{margin-left:auto;font-size:11.5px;font-weight:600;color:#9a6700;background:#fff8c5;border:1px solid #d4a72c;border-radius:10px;padding:1px 9px}
table{border-collapse:collapse;width:100%%;table-layout:fixed}
td,th{border:1px solid var(--line);padding:3px 7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;height:25px}
th{background:var(--head);color:var(--muted);font-weight:400;font-size:12px;text-align:center}
td.n{background:var(--head);color:var(--muted);text-align:center;font-size:12px}
tr.h td:not(.n){background:#e6f4ea;font-weight:600}
td.r{text-align:right}
.tabs{display:flex;gap:2px;padding:6px 10px;background:var(--head);border-top:1px solid var(--line);font-size:13px}
.tab{padding:5px 14px;border-radius:4px 4px 0 0;color:var(--muted)}
.tab.on{background:#fff;color:var(--bar);font-weight:600;box-shadow:inset 0 -2px 0 var(--bar)}
"""

JS = "document.body.dataset.h=Math.ceil(document.querySelector('.sheet').getBoundingClientRect().height);"
LETTERS = "ABCDEFGHIJKL"


def table_page(title: str, tab: str, rows: list[list], widths: list[int], right: set[int], min_rows: int) -> str:
    width = 46 + sum(widths)
    cols = "".join(f'<th style="width:{w}px">{LETTERS[i]}</th>' for i, w in enumerate(widths))
    body = []
    for number in range(1, max(len(rows), min_rows) + 1):
        row = rows[number - 1] if number <= len(rows) else []
        cells = "".join(
            f'<td class="{"r" if i in right and number > 1 else ""}">{escape(_text(row[i])) if i < len(row) else ""}</td>'
            for i in range(len(widths))
        )
        body.append(f'<tr class="{"h" if number == 1 else ""}"><td class="n">{number}</td>{cells}</tr>')
    tabs = "".join(f'<div class="tab{" on" if t == tab else ""}">{t}</div>' for t in (ORDERS_TAB, MENU_TAB))
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title><style>{CSS % {'width': width}}</style></head><body><div class=\"sheet\">"
        f'<div class="top"><div class="logo"></div><div><div class="name">{escape(title)}</div>'
        '<div class="sub">Tab as the bot reads and writes it</div></div><div class="demo">demo data</div></div>'
        f'<table><colgroup><col style="width:46px">{"".join(f'<col style="width:{w}px">' for w in widths)}</colgroup>'
        f'<tr><th></th>{cols}</tr>{"".join(body)}</table><div class="tabs">{tabs}</div></div>'
        f"<script>{JS}</script></body></html>\n"
    )


def _text(value) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


async def run_demo() -> tuple[list[list], list[list]]:
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            _env_file=None, bot_token="42:" + "A" * 35, admin_ids=[ADMIN_ID], db_path=str(Path(tmp) / "demo.db"),
            payment_details=PAYMENT_DETAILS, timezone="Europe/Berlin",
        )
        engine, sessionmaker = create_engine_and_sessionmaker(settings.db_url)
        await init_db(engine)
        await seed(sessionmaker)
        sheet = MemorySheet()
        sheets = SheetsSync(sheet, settings, retry_delays=())
        s = Scenario(settings, sessionmaker, sheets)
        c, a = (CUSTOMER_ID, CUSTOMER_NAME), (ADMIN_ID, "Sam Admin")

        await s.say(*a, "/start")
        await s.say(*c, "/start")
        await s.say(*c, "/catalog")
        await s.tap(*c, "Tea")
        await s.tap(*c, "Add to cart", near="Alpine Green Tea")
        await s.tap(*c, "Add to cart", near="Alpine Green Tea")
        await s.tap(*c, "Back")
        await s.tap(*c, "Candles")
        await s.tap(*c, "Add to cart", near="Pine Forest Candle")
        await s.tap(*c, "Cart")
        await s.tap(*c, "Checkout")
        for text in (CUSTOMER_NAME, CUSTOMER_PHONE, CUSTOMER_ADDRESS):
            await s.say(*c, text)
        await s.tap(*c, "Cash on delivery")
        await s.tap(*c, "Confirm")

        await s.say(*c, "/catalog")
        await s.tap(*c, "Home and Gifts")
        await s.tap(*c, "Add to cart", near="Gift Box")
        await s.tap(*c, "Cart")
        await s.tap(*c, "Checkout")
        for text in ("Maya Ortiz", "+1 555 0142", "7 Cedar Court, Springfield"):
            await s.say(*c, text)
        await s.tap(*c, "Bank transfer")
        await s.send_photo(*c, RECEIPT_FILE_ID)
        await s.tap(*c, "Confirm")
        await sheets.drain()

        # The owner types a new status into the first order's row; the next sync applies it.
        sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, "confirmed")
        await sheets.sync_statuses(s.bot, sessionmaker)
        orders = [list(r) for r in sheet.tabs[ORDERS_TAB]]

        # Menu: the empty tab is filled from the catalog, then the owner edits it.
        await sheets.sync_menu(sessionmaker)
        menu = sheet.tabs[MENU_TAB]
        menu[1][3] = 14.0                      # Alpine Green Tea gets a new price
        menu[4][5] = "no"                      # Pine Forest Candle sold out
        menu.append(["Tea", "Jasmine Pearls, 80 g", "Hand-rolled green tea scented with jasmine.", 15.5, "", "yes"])
        menu.append(["Candles", "Cedar Votive", "Small candle", "free", "", "yes"])  # bad price: skipped
        await sheets.sync_menu(sessionmaker)
        await engine.dispose()
        return orders, [list(r) for r in menu]


def main() -> None:
    orders, menu = asyncio.run(run_demo())
    pages = {
        "11-sheet-orders": table_page("Maple & Pine Goods - orders", ORDERS_TAB, orders,
                                      [70, 120, 110, 120, 200, 330, 70, 120, 70, 90], {0, 6}, 8),
        "12-sheet-menu": table_page("Maple & Pine Goods - menu", MENU_TAB, menu,
                                    [120, 190, 330, 70, 220, 90], {3}, 14),
    }
    SHOTS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, html in pages.items():
            path = Path(tmp) / f"{name}.html"
            path.write_text(html, encoding="utf-8")
            width = int(re.search(r"\.sheet\{width:(\d+)px", html).group(1))
            match = re.search(r'data-h="(\d+)"', edge("--dump-dom", f"--window-size={width},800", path.as_uri()))
            if match is None:
                raise RuntimeError(f"could not measure {name}")
            out = SHOTS / f"{name}.png"
            edge(f"--window-size={width},{int(match.group(1)) + 2}", f"--screenshot={out}", path.as_uri())
            print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
