"""In-memory sheet with the same interface as the Google one: used by the tests and the demo screenshots."""
from __future__ import annotations


class MemorySheet:
    def __init__(self) -> None:
        self.tabs: dict[str, list[list]] = {}
        self.calls: list[tuple] = []
        # Raise this many times from the next calls (any method), to simulate an outage.
        self.fail_next = 0

    def _enter(self, *call) -> None:
        self.calls.append(call)
        if self.fail_next:
            self.fail_next -= 1
            raise ConnectionError("sheet unavailable")

    def ensure_tab(self, tab: str, header: list[str]) -> None:
        self._enter("ensure_tab", tab)
        rows = self.tabs.setdefault(tab, [])
        if not rows or not any(str(c).strip() for c in rows[0]):
            rows[:1] = [list(header)]

    def read_rows(self, tab: str) -> list[list[str]]:
        self._enter("read_rows", tab)
        return [["" if c is None else str(c) for c in row] for row in self.tabs.get(tab, [])]

    def append_rows(self, tab: str, rows: list[list]) -> None:
        self._enter("append_rows", tab)
        self.tabs.setdefault(tab, []).extend(list(r) for r in rows)

    def update_cell(self, tab: str, row: int, col: int, value: str) -> None:
        self._enter("update_cell", tab)
        grid = self.tabs[tab]
        line = grid[row - 1]
        line.extend([""] * (col - len(line)))
        line[col - 1] = value

    # Helpers for tests and demos: what the sheet owner does by hand, without being counted as a bot call.
    def set_cell(self, tab: str, row: int, col: int, value: str) -> None:
        line = self.tabs[tab][row - 1]
        line.extend([""] * (col - len(line)))
        line[col - 1] = value

    def set_rows(self, tab: str, rows: list[list]) -> None:
        self.tabs[tab] = [list(r) for r in rows]
