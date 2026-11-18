"""Google Sheets through gspread and a service account. gspread is imported on first use only."""
from __future__ import annotations


class GspreadBackend:
    def __init__(self, sheet_id: str, credentials_file: str):
        self.sheet_id = sheet_id
        self.credentials_file = credentials_file
        self._book = None

    def _spreadsheet(self):
        if self._book is None:  # connect lazily so a bad key or a network outage is retried, not fatal at startup
            import gspread

            client = gspread.service_account(filename=self.credentials_file)
            self._book = client.open_by_key(self.sheet_id)
        return self._book

    def _find(self, tab: str):
        import gspread

        try:
            return self._spreadsheet().worksheet(tab)
        except gspread.WorksheetNotFound:
            return None

    def ensure_tab(self, tab: str, header: list[str]) -> None:
        sheet = self._find(tab)
        if sheet is None:
            sheet = self._spreadsheet().add_worksheet(title=tab, rows=1000, cols=len(header))
        first = sheet.row_values(1)
        if not any(cell.strip() for cell in first):
            sheet.update(values=[header], range_name="A1", value_input_option="RAW")

    def read_rows(self, tab: str) -> list[list[str]]:
        from gspread.utils import ValueRenderOption

        sheet = self._find(tab)
        if sheet is None:
            return []
        # Unformatted, so a price shown as "$12.50" arrives as 12.5.
        rows = sheet.get_all_values(value_render_option=ValueRenderOption.unformatted)
        return [[str(cell) for cell in row] for row in rows]

    def append_rows(self, tab: str, rows: list[list]) -> None:
        self._worksheet(tab).append_rows(rows, value_input_option="RAW", table_range="A1")

    def update_cell(self, tab: str, row: int, col: int, value: str) -> None:
        from gspread.utils import rowcol_to_a1

        self._worksheet(tab).update(values=[[value]], range_name=rowcol_to_a1(row, col), value_input_option="RAW")

    def _worksheet(self, tab: str):
        sheet = self._find(tab)
        if sheet is None:
            raise LookupError(f"tab {tab!r} does not exist")
        return sheet
