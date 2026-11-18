"""Google Sheets integration, against an in-memory sheet (no network, no gspread)."""
import sys

import pytest
from sqlalchemy import select

from app.callbacks import Confirm, OrderStatusCb
from app.config import Settings
from app.db.models import Category, Order, Product
from app.i18n import EN
from app.sheets import SheetsSync, create_sheets
from app.sheets.backend import MENU_HEADER, MENU_TAB, ORDERS_HEADER, ORDERS_TAB, STATUS_COL
from app.sheets.memory import MemorySheet
from tests.conftest import ADMIN_ID, CUSTOMER_ID, Harness
from tests.test_handlers import _db, _place_order
from tests.test_receipts import _to_receipt_step


@pytest.fixture
def sheet() -> MemorySheet:
    return MemorySheet()


@pytest.fixture
def sheets(sheet, settings) -> SheetsSync:
    return SheetsSync(sheet, settings.model_copy(update={"timezone": "Europe/Berlin"}), retry_delays=(0, 0))


@pytest.fixture
def sheet_harness(settings, seeded, sheets) -> Harness:
    return Harness(settings, seeded, sheets)


async def _checkout(h: Harness, sheets: SheetsSync) -> None:
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    await sheets.drain()


def _status(sheet: MemorySheet, row: int = 2) -> str:
    return sheet.tabs[ORDERS_TAB][row - 1][STATUS_COL - 1]


# --- orders -> sheet ------------------------------------------------------------------------------

async def test_confirmed_order_is_appended_with_all_columns(sheet_harness, sheets, sheet):
    await _checkout(sheet_harness, sheets)
    header, row = sheet.tabs[ORDERS_TAB]
    assert header == ORDERS_HEADER
    order = (await _db(sheet_harness, select(Order)))[0]
    assert row[0] == order.id and row[2:] == [
        "Ann Lee", "+15551234567", "12 Birch Street, Springfield",
        "Alpine Green Tea, 100 g x 2", 25.0, "Cash on delivery", "no", "new",
    ]
    assert len(row[1]) == 16


async def test_receipt_and_transfer_are_reported(settings, seeded, sheets, sheet):
    h = Harness(settings, seeded, sheets)
    await _to_receipt_step(h)
    await h.send_photo(CUSTOMER_ID, "AgACphoto")
    await h.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))
    await sheets.drain()
    row = sheet.tabs[ORDERS_TAB][1]
    assert row[7:9] == ["Bank transfer", "yes"]


async def test_sheet_failure_does_not_break_checkout_and_is_retried(sheet_harness, sheets, sheet, caplog):
    sheet.fail_next = 2  # the first two attempts fail, the third works
    await sheet_harness.say(ADMIN_ID, "/start")
    await _place_order(sheet_harness)
    assert any("Thank you" in e.text for e in sheet_harness.edits())
    assert len(await _db(sheet_harness, select(Order))) == 1  # saved regardless of the sheet
    assert sheet_harness.texts_to(ADMIN_ID)
    await sheets.drain()
    assert len(sheet.tabs[ORDERS_TAB]) == 2
    assert "retry" in caplog.text


async def test_sheet_outage_is_logged_and_the_order_stays_in_the_database(sheet_harness, sheets, sheet, caplog):
    sheet.fail_next = 100
    await _checkout(sheet_harness, sheets)
    assert len(await _db(sheet_harness, select(Order))) == 1
    assert ORDERS_TAB not in sheet.tabs or len(sheet.tabs[ORDERS_TAB]) <= 1
    assert "giving up on order 1" in caplog.text


async def test_status_changed_by_admin_button_updates_the_sheet(sheet_harness, sheets, sheet):
    await _checkout(sheet_harness, sheets)
    await sheet_harness.press(ADMIN_ID, OrderStatusCb(order_id=1, status="confirmed"))
    await sheets.drain()
    assert _status(sheet) == "confirmed"


# --- feature off -----------------------------------------------------------------------------------

async def test_checkout_without_sheets_makes_no_sheet_calls(harness, sheet):
    await harness.say(ADMIN_ID, "/start")
    await _place_order(harness)
    assert len(await _db(harness, select(Order))) == 1
    assert harness.dp.workflow_data["sheets"] is None
    assert sheet.calls == []


def test_sheets_are_off_unless_both_settings_are_present(caplog):
    assert create_sheets(Settings(_env_file=None)) is None
    assert create_sheets(Settings(_env_file=None, google_sheet_id="abc")) is None
    assert "Google Sheets is off" in caplog.text
    assert "gspread" not in sys.modules


def test_sync_interval_has_a_floor():
    assert Settings(_env_file=None).sheets_sync_seconds == 60
    with pytest.raises(ValueError):
        Settings(_env_file=None, sheets_sync_seconds=1)


# --- menu <- sheet ---------------------------------------------------------------------------------

def _menu(sheet: MemorySheet, *rows) -> None:
    sheet.set_rows(MENU_TAB, [MENU_HEADER, *rows])


async def _products(h) -> dict[str, Product]:
    return {p.name: p for p in await _db(h, select(Product))}


async def test_empty_menu_tab_is_started_from_the_catalog(sheet_harness, sheets, sheet):
    await sheets.sync_menu(sheet_harness.dp.workflow_data["sessionmaker"])
    rows = sheet.tabs[MENU_TAB]
    assert rows[0] == MENU_HEADER and len(rows) == 10
    assert rows[1] == ["Tea", "Alpine Green Tea, 100 g", "Light, grassy green tea with a clean finish. Loose leaf.",
                       12.5, "", "yes"]


async def test_menu_sync_adds_updates_and_hides_products(sheet_harness, sheets, sheet):
    sm = sheet_harness.dp.workflow_data["sessionmaker"]
    _menu(
        sheet,
        ["Tea", "Alpine Green Tea, 100 g", "Fresh lot", "14,00", "", "yes"],     # price and text changed
        ["Candles", "Pine Forest Candle", "", "19", "", "no"],                    # hidden by the owner
        ["Tea", "Jasmine Pearls", "Rolled by hand", "9.90", "https://x.test/j.jpg", "yes"],  # new product
        ["Spices", "Smoked Paprika", "", "4.5", "", ""],                          # new category, blank = available
    )
    await sheets.sync_menu(sm)
    products = await _products(sheet_harness)
    tea = products["Alpine Green Tea, 100 g"]
    assert (tea.price_cents, tea.description, tea.is_active) == (1400, "Fresh lot", True)
    assert products["Pine Forest Candle"].is_active is False
    jasmine = products["Jasmine Pearls"]
    assert (jasmine.price_cents, jasmine.image_url, jasmine.category_id) == (990, "https://x.test/j.jpg", tea.category_id)
    cats = {c.name_en: c for c in await _db(sheet_harness, select(Category))}
    assert products["Smoked Paprika"].category_id == cats["Spices"].id and cats["Spices"].sort == 3
    # everything else is no longer listed, so it is hidden, but still in the database
    assert products["Linen Tea Towel"].is_active is False
    assert len(products) == 11


async def test_menu_sync_skips_bad_rows_and_logs_them(sheet_harness, sheets, sheet, caplog):
    sm = sheet_harness.dp.workflow_data["sessionmaker"]
    _menu(
        sheet,
        ["Tea", "Alpine Green Tea, 100 g", "", "abc", "", "yes"],
        ["Tea", "Smoked Black Tea, 100 g", "", "-3", "", "yes"],
        ["Tea", "Mint and Lemon Blend, 80 g", "", "11", "", "maybe"],
        ["", "No category", "", "5", "", "yes"],
        ["Tea", "", "", "5", "", "yes"],
        ["Tea", "Ceramic Tea Mug", "", "16", "", "yes"],
        ["Tea", "ceramic tea mug", "", "17", "", "yes"],
        [],
    )
    await sheets.sync_menu(sm)
    products = await _products(sheet_harness)
    assert products["Alpine Green Tea, 100 g"].price_cents == 1250  # untouched by the bad row
    assert products["Ceramic Tea Mug"].price_cents == 1600
    assert products["Ceramic Tea Mug"].category_id == 1  # the valid row moved it into Tea
    assert "No category" not in products
    for number in (2, 3, 4, 5, 6, 8):
        assert f"Menu row {number}" in caplog.text


async def test_menu_with_only_bad_rows_does_not_hide_the_whole_catalog(sheet_harness, sheets, sheet):
    _menu(sheet, ["Tea", "Anything", "", "free", "", "yes"])
    await sheets.sync_menu(sheet_harness.dp.workflow_data["sessionmaker"])
    assert all(p.is_active for p in await _db(sheet_harness, select(Product)))


async def test_hidden_products_keep_old_orders(sheet_harness, sheets, sheet):
    await _checkout(sheet_harness, sheets)
    _menu(sheet, ["Tea", "Mint and Lemon Blend, 80 g", "", "11", "", "yes"])
    await sheets.sync_menu(sheet_harness.dp.workflow_data["sessionmaker"])
    order = (await _db(sheet_harness, select(Order)))[0]
    assert order.items[0].name == "Alpine Green Tea, 100 g" and order.items[0].unit_price_cents == 1250
    product = (await _products(sheet_harness))["Alpine Green Tea, 100 g"]
    assert product.is_active is False


async def test_empty_photo_cell_keeps_the_existing_photo(sheet_harness, sheets, sheet):
    _menu(sheet, ["Candles", "Pine Forest Candle", "", "19", "", "yes"])
    await sheets.sync_menu(sheet_harness.dp.workflow_data["sessionmaker"])
    assert (await _products(sheet_harness))["Pine Forest Candle"].image_url.startswith("https://placehold.co")


async def test_menu_sync_failure_is_logged_not_raised(sheet_harness, sheets, sheet, caplog):
    sheet.fail_next = 1
    await sheets.sync_once(sheet_harness.bot, sheet_harness.dp.workflow_data["sessionmaker"])
    assert "menu sync failed" in caplog.text


async def test_menu_sync_can_be_switched_off(settings, seeded, sheet):
    off = SheetsSync(sheet, settings.model_copy(update={"sheets_menu_sync": False}), retry_delays=())
    h = Harness(settings, seeded, off)
    await off.sync_once(h.bot, seeded)
    assert MENU_TAB not in sheet.tabs


# --- status <- sheet -------------------------------------------------------------------------------

async def test_status_set_in_the_sheet_is_applied_and_the_customer_is_told(sheet_harness, sheets, sheet):
    await _checkout(sheet_harness, sheets)
    before = len(sheet_harness.texts_to(CUSTOMER_ID))
    sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, " Confirmed ")
    await sheets.sync_statuses(sheet_harness.bot, sheet_harness.dp.workflow_data["sessionmaker"])
    assert (await _db(sheet_harness, select(Order)))[0].status == "confirmed"
    sent = sheet_harness.texts_to(CUSTOMER_ID)[before:]
    assert sent == [EN["order_status_update"].format(id=1, status=EN["status_confirmed"])]


async def test_sheet_status_follows_the_allowed_transitions(sheet_harness, sheets, sheet, caplog):
    await _checkout(sheet_harness, sheets)
    sm = sheet_harness.dp.workflow_data["sessionmaker"]
    before = len(sheet_harness.texts_to(CUSTOMER_ID))
    sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, "delivered")  # new -> delivered is not allowed
    await sheets.sync_statuses(sheet_harness.bot, sm)
    assert (await _db(sheet_harness, select(Order)))[0].status == "new"
    assert _status(sheet) == "new"  # the cell is put back
    assert "ignored status 'delivered'" in caplog.text
    assert len(sheet_harness.texts_to(CUSTOMER_ID)) == before

    sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, "cancelled")
    await sheets.sync_statuses(sheet_harness.bot, sm)
    sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, "new")  # cancelled is final
    await sheets.sync_statuses(sheet_harness.bot, sm)
    assert (await _db(sheet_harness, select(Order)))[0].status == "cancelled"
    assert _status(sheet) == "cancelled"


async def test_invalid_status_text_is_ignored_and_logged(sheet_harness, sheets, sheet, caplog):
    await _checkout(sheet_harness, sheets)
    before = len(sheet_harness.texts_to(CUSTOMER_ID))
    sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, "on the way")
    await sheets.sync_statuses(sheet_harness.bot, sheet_harness.dp.workflow_data["sessionmaker"])
    assert (await _db(sheet_harness, select(Order)))[0].status == "new"
    assert "ignored status 'on the way'" in caplog.text
    assert len(sheet_harness.texts_to(CUSTOMER_ID)) == before


async def test_unknown_order_rows_and_blank_statuses_are_skipped(sheet_harness, sheets, sheet, caplog):
    await _checkout(sheet_harness, sheets)
    sheet.tabs[ORDERS_TAB].append(["99", "", "", "", "", "", 1, "", "no", "shipped"])
    sheet.tabs[ORDERS_TAB].append(["x", "", "", "", "", "", 1, "", "no", "shipped"])
    sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, "")
    await sheets.sync_statuses(sheet_harness.bot, sheet_harness.dp.workflow_data["sessionmaker"])
    assert (await _db(sheet_harness, select(Order)))[0].status == "new"
    assert "unknown order '99'" in caplog.text


async def test_status_sync_waits_while_writes_are_pending(sheet_harness, sheets, sheet):
    await _checkout(sheet_harness, sheets)
    sheet.set_cell(ORDERS_TAB, 2, STATUS_COL, "confirmed")
    sheets.order_status_changed(1, "new")  # a queued write
    calls = len(sheet.calls)
    await sheets.sync_once(sheet_harness.bot, sheet_harness.dp.workflow_data["sessionmaker"])
    assert (await _db(sheet_harness, select(Order)))[0].status == "new"
    await sheets.drain()
    assert len(sheet.calls) > calls


# --- Google backend (gspread replaced by a stub) -----------------------------------------------------

class _Worksheet:
    def __init__(self, title):
        self.title, self.first_row, self.calls = title, [], []

    def row_values(self, n):
        return self.first_row

    def update(self, **kwargs):
        self.calls.append(("update", kwargs))

    def append_rows(self, rows, **kwargs):
        self.calls.append(("append_rows", rows, kwargs))

    def get_all_values(self, **kwargs):
        return [["Order ID"], [5, 1.5]]


def test_gspread_backend_talks_to_the_worksheet_api(monkeypatch):
    import types

    book = types.SimpleNamespace(sheets={}, opened=[])

    class NotFound(Exception):
        pass

    def worksheet(title):
        if title not in book.sheets:
            raise NotFound
        return book.sheets[title]

    def add_worksheet(title, rows, cols):
        book.sheets[title] = _Worksheet(title)
        return book.sheets[title]

    book.worksheet, book.add_worksheet = worksheet, add_worksheet
    client = types.SimpleNamespace(open_by_key=lambda key: book.opened.append(key) or book)
    stub = types.ModuleType("gspread")
    stub.WorksheetNotFound = NotFound
    stub.service_account = lambda filename: client
    utils = types.ModuleType("gspread.utils")
    utils.ValueRenderOption = types.SimpleNamespace(unformatted="UNFORMATTED_VALUE")
    utils.rowcol_to_a1 = lambda row, col: f"{'ABCDEFGHIJ'[col - 1]}{row}"
    monkeypatch.setitem(sys.modules, "gspread", stub)
    monkeypatch.setitem(sys.modules, "gspread.utils", utils)

    from app.sheets.gspread_backend import GspreadBackend

    backend = GspreadBackend("sheet-id", "key.json")
    assert backend.read_rows("Orders") == []
    backend.ensure_tab("Orders", ["a", "b"])
    backend.append_rows("Orders", [[1, "x"]])
    backend.update_cell("Orders", 2, 10, "shipped")
    assert book.opened == ["sheet-id"]  # connected once, on first use
    kinds = [c[0] for c in book.sheets["Orders"].calls]
    assert kinds == ["update", "append_rows", "update"]
    assert book.sheets["Orders"].calls[0][1]["range_name"] == "A1"
    assert book.sheets["Orders"].calls[1][2]["value_input_option"] == "RAW"
    assert book.sheets["Orders"].calls[2][1] == {"values": [["shipped"]], "range_name": "J2", "value_input_option": "RAW"}
    assert backend.read_rows("Orders") == [["Order ID"], ["5", "1.5"]]
