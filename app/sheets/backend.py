"""What the bot needs from a spreadsheet. The real one is gspread, tests use an in-memory sheet."""
from __future__ import annotations

from typing import Protocol

ORDERS_TAB = "Orders"
MENU_TAB = "Menu"

ORDERS_HEADER = ["Order ID", "Created", "Customer", "Phone", "Address", "Items", "Total", "Payment", "Receipt", "Status"]
MENU_HEADER = ["Category", "Name", "Description", "Price", "Photo", "Available"]

ORDER_ID_COL = 1
STATUS_COL = 10  # 1-based, like the sheet itself


class SheetBackend(Protocol):
    """Blocking calls (gspread is synchronous); SheetsSync runs them in a worker thread, one at a time."""

    def ensure_tab(self, tab: str, header: list[str]) -> None:
        """Create the tab if it is missing and write the header if the first row is empty."""

    def read_rows(self, tab: str) -> list[list[str]]:
        """Every row including the header, cells as plain strings. Missing tab: empty list."""

    def append_rows(self, tab: str, rows: list[list]) -> None:
        """Add rows below the last used row. Cells are stored as given, never parsed as formulas."""

    def update_cell(self, tab: str, row: int, col: int, value: str) -> None:
        """1-based row and column."""
