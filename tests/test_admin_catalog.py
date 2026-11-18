"""Admin catalog management: product delete, category add / rename / guarded delete, schema upgrade."""
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.callbacks import (
    AddToCart,
    AdminNav,
    Cat,
    CartAct,
    CategoryDelete,
    CategoryEdit,
    CategoryNew,
    Confirm,
    EditField,
    Menu,
    PickCategory,
    ProductDelete,
    ProductEdit,
)
from app.config import Settings
from app.db.models import CartItem, Category, Order, OrderItem, Product
from app.db.session import create_engine_and_sessionmaker, init_db
from app.i18n import EN
from app.services.catalog import CategoryNotEmpty, delete_category, delete_product
from tests.conftest import ADMIN_ID, CUSTOMER_ID
from tests.test_handlers import _db, _place_order


def _buttons(message):
    return [b for row in message.reply_markup.inline_keyboard for b in row]


async def test_delete_product_asks_first_and_keeps_past_orders_intact(harness):
    await _place_order(harness)  # 2 x Alpine Green Tea
    await harness.press(CUSTOMER_ID, AddToCart(product_id=1))  # and one more sits in a cart

    await harness.press(ADMIN_ID, ProductDelete(product_id=1))
    assert "Alpine Green Tea" in harness.edits()[-1].text
    assert len(await _db(harness, select(Product))) == 9, "nothing deleted before the confirmation"

    await harness.press(ADMIN_ID, ProductDelete(product_id=1, confirmed=True))
    assert EN["product_deleted"] in harness.alerts()
    assert await _db(harness, select(Product).where(Product.id == 1)) == []
    assert await _db(harness, select(CartItem)) == []
    [line] = await _db(harness, select(OrderItem))
    assert (line.name, line.quantity, line.product_id) == ("Alpine Green Tea, 100 g", 2, None)
    assert (await _db(harness, select(Order)))[0].total_cents == 2500

    await harness.press(CUSTOMER_ID, CartAct(action="checkout"))
    assert EN["cart_empty"] in harness.alerts()


async def test_delete_product_cancel_returns_to_the_list(harness):
    await harness.press(ADMIN_ID, ProductDelete(product_id=2))
    await harness.press(ADMIN_ID, AdminNav(section="products"))
    assert "Products" in harness.edits()[-1].text
    assert len(await _db(harness, select(Product))) == 9


async def test_customers_cannot_delete_products(harness):
    await harness.press(CUSTOMER_ID, ProductDelete(product_id=1, confirmed=True))
    assert EN["stale_button"] in harness.alerts()
    assert len(await _db(harness, select(Product))) == 9


async def test_delete_unknown_product_is_a_stale_button(harness):
    await harness.press(ADMIN_ID, ProductDelete(product_id=99, confirmed=True))
    assert EN["stale_button"] in harness.alerts()


async def test_categories_command_lists_categories_for_admins_only(harness):
    await harness.say(CUSTOMER_ID, "/categories")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["no_permission"]

    await harness.say(ADMIN_ID, "/categories")
    message = harness.sent_to(ADMIN_ID)[-1]
    labels = [b.text for b in _buttons(message)]
    assert "✏️ Tea" in labels and "✏️ Candles" in labels and EN["btn_add_category"] in labels


async def test_add_category_flow(harness):
    await harness.say(ADMIN_ID, "/categories")
    await harness.press(ADMIN_ID, CategoryNew())
    assert harness.texts_to(ADMIN_ID)[-1] == EN["category_ask_en"]
    await harness.say(ADMIN_ID, "x" * 65)
    assert harness.texts_to(ADMIN_ID)[-1] == EN["invalid_text"]
    await harness.say(ADMIN_ID, "Soap")
    assert harness.texts_to(ADMIN_ID)[-1] == EN["category_ask_ru"]
    await harness.say(ADMIN_ID, "Мыло")

    cats = await _db(harness, select(Category).order_by(Category.id))
    assert [(c.name_en, c.name_ru, c.sort) for c in cats][-1] == ("Soap", "Мыло", 3)
    assert EN["category_saved"] in harness.texts_to(ADMIN_ID)
    assert "✏️ Soap" in [b.text for b in _buttons(harness.sent_to(ADMIN_ID)[-1])]


async def test_new_category_shows_up_for_customers_and_in_the_product_form(harness):
    await harness.press(ADMIN_ID, CategoryNew())
    await harness.say(ADMIN_ID, "Soap")
    await harness.say(ADMIN_ID, "Мыло")
    await harness.press(CUSTOMER_ID, Menu(action="catalog"))
    assert "Soap" in [b.text for b in _buttons_of_last_edit(harness)]
    await harness.say(ADMIN_ID, "/add_product")
    assert "Soap" in [b.text for b in _buttons(harness.sent_to(ADMIN_ID)[-1])]


def _buttons_of_last_edit(harness):
    markup = harness.edits()[-1].reply_markup
    return [b for row in markup.inline_keyboard for b in row]


async def test_rename_category_can_keep_one_of_the_names(harness):
    await harness.press(ADMIN_ID, CategoryEdit(category_id=1))
    assert "Tea" in harness.texts_to(ADMIN_ID)[-1]
    await harness.say(ADMIN_ID, "Loose Tea")
    await harness.say(ADMIN_ID, "-")  # keep the Russian name

    cat = (await _db(harness, select(Category).where(Category.id == 1)))[0]
    assert (cat.name_en, cat.name_ru) == ("Loose Tea", "Чай")


async def test_rename_category_with_dash_for_english_keeps_it(harness):
    await harness.press(ADMIN_ID, CategoryEdit(category_id=2))
    await harness.say(ADMIN_ID, "-")
    await harness.say(ADMIN_ID, "Свечки")
    cat = (await _db(harness, select(Category).where(Category.id == 2)))[0]
    assert (cat.name_en, cat.name_ru) == ("Candles", "Свечки")


async def test_dash_is_not_a_valid_name_when_adding(harness):
    await harness.press(ADMIN_ID, CategoryNew())
    await harness.say(ADMIN_ID, "-")
    assert harness.texts_to(ADMIN_ID)[-1] == EN["invalid_text"]


async def test_non_empty_category_cannot_be_deleted(harness):
    await harness.press(ADMIN_ID, CategoryDelete(category_id=1))
    assert EN["category_not_empty"].format(count=3) in harness.alerts()
    await harness.press(ADMIN_ID, CategoryDelete(category_id=1, confirmed=True))
    assert len(await _db(harness, select(Category))) == 3


async def test_empty_category_is_deleted_after_confirmation(harness):
    await harness.press(ADMIN_ID, CategoryNew())
    await harness.say(ADMIN_ID, "Soap")
    await harness.say(ADMIN_ID, "Мыло")
    new_id = (await _db(harness, select(Category).where(Category.name_en == "Soap")))[0].id

    await harness.press(ADMIN_ID, CategoryDelete(category_id=new_id))
    assert "Soap" in harness.edits()[-1].text
    assert len(await _db(harness, select(Category))) == 4
    await harness.press(ADMIN_ID, CategoryDelete(category_id=new_id, confirmed=True))
    assert EN["category_deleted"] in harness.alerts()
    assert len(await _db(harness, select(Category))) == 3


async def test_customers_cannot_touch_categories(harness):
    await harness.press(CUSTOMER_ID, CategoryNew())
    await harness.press(CUSTOMER_ID, CategoryDelete(category_id=3, confirmed=True))
    assert harness.alerts().count(EN["stale_button"]) == 2
    assert len(await _db(harness, select(Category))) == 3


async def test_edit_product_category_moves_the_product(harness):
    await harness.say(ADMIN_ID, "/edit_product")
    await harness.press(ADMIN_ID, ProductEdit(product_id=1))
    await harness.press(ADMIN_ID, EditField(field="category"))
    assert harness.texts_to(ADMIN_ID)[-1] == EN["edit_ask_category"]
    await harness.press(ADMIN_ID, PickCategory(category_id=3))
    assert (await _db(harness, select(Product).where(Product.id == 1)))[0].category_id == 3
    assert EN["product_updated"] in harness.texts_to(ADMIN_ID)[-1]


async def test_moving_products_out_unlocks_category_delete(harness, seeded):
    async with seeded() as s:
        for pid in (1, 2, 3):
            (await s.get(Product, pid)).category_id = 3
        await s.commit()
    await harness.press(ADMIN_ID, CategoryDelete(category_id=1, confirmed=True))
    assert [c.id for c in await _db(harness, select(Category).order_by(Category.id))] == [2, 3]


async def test_category_service_guards_non_empty_and_unknown(seeded):
    async with seeded() as s:
        with pytest.raises(CategoryNotEmpty) as exc:
            await delete_category(s, 1)
        assert exc.value.count == 3
        assert await delete_category(s, 99) is False
        assert await delete_product(s, 99) is False
        assert await delete_product(s, 1) is True


OLD_ORDERS_TABLE = """
CREATE TABLE orders (
    id INTEGER NOT NULL PRIMARY KEY, user_id BIGINT NOT NULL, customer_name VARCHAR(120) NOT NULL,
    phone VARCHAR(32) NOT NULL, address TEXT NOT NULL, payment_method VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL, total_cents INTEGER NOT NULL, created_at DATETIME NOT NULL
)
"""


async def test_init_db_adds_receipt_columns_to_an_existing_database(tmp_path):
    settings = Settings(_env_file=None, db_path=str(tmp_path / "old.db"))
    raw = create_async_engine(settings.db_url)
    async with raw.begin() as conn:
        await conn.execute(text(OLD_ORDERS_TABLE))
        await conn.execute(text(
            "INSERT INTO orders VALUES (1, 5, 'Old Customer', '+15550000', 'Somewhere 1', 'cash', 'new', 1250,"
            " '2025-01-01 10:00:00')"
        ))
    await raw.dispose()

    engine, sessionmaker = create_engine_and_sessionmaker(settings.db_url)
    await init_db(engine)
    await init_db(engine)  # running it again is harmless
    async with sessionmaker() as s:
        order = (await s.scalars(select(Order))).one()
        assert (order.customer_name, order.total_cents) == ("Old Customer", 1250)
        assert (order.receipt_file_id, order.receipt_type) == (None, None)
        order.receipt_file_id, order.receipt_type = "file", "photo"
        await s.commit()
    await engine.dispose()


async def test_add_product_with_an_uploaded_photo(harness):
    await harness.say(ADMIN_ID, "/add_product")
    await harness.press(ADMIN_ID, PickCategory(category_id=2))
    await harness.say(ADMIN_ID, "Beeswax Candle")
    await harness.say(ADMIN_ID, "15.50")
    await harness.say(ADMIN_ID, "Natural beeswax.")
    await harness.send_photo(ADMIN_ID, "AgACcandle")
    assert EN["image_photo"] in harness.texts_to(ADMIN_ID)[-1]
    await harness.press(ADMIN_ID, Confirm(ctx="product", ok=True))

    created = (await _db(harness, select(Product).where(Product.name == "Beeswax Candle")))[0]
    assert created.image_url == "AgACcandle"

    await harness.press(CUSTOMER_ID, Cat(id=2))
    card = [c for c in harness.sent_to(CUSTOMER_ID) if type(c).__name__ == "SendPhoto" and "Beeswax" in c.caption]
    assert card and card[0].photo == "AgACcandle"


async def test_edit_product_image_with_a_photo(harness):
    await harness.press(ADMIN_ID, ProductEdit(product_id=3))
    await harness.press(ADMIN_ID, EditField(field="image"))
    await harness.send_photo(ADMIN_ID, "AgACnew")
    assert (await _db(harness, select(Product).where(Product.id == 3)))[0].image_url == "AgACnew"
    assert EN["product_updated"] in harness.texts_to(ADMIN_ID)[-1]


async def test_photo_for_a_non_image_field_is_refused_and_typing_a_category_is_redirected(harness):
    await harness.press(ADMIN_ID, ProductEdit(product_id=3))
    await harness.press(ADMIN_ID, EditField(field="price"))
    await harness.send_photo(ADMIN_ID)
    assert harness.texts_to(ADMIN_ID)[-1] == EN["text_expected"]

    await harness.say(ADMIN_ID, "/edit_product")
    await harness.press(ADMIN_ID, ProductEdit(product_id=3))
    await harness.press(ADMIN_ID, EditField(field="category"))
    await harness.say(ADMIN_ID, "Candles")
    assert harness.texts_to(ADMIN_ID)[-1] == EN["edit_ask_category"]
    assert (await _db(harness, select(Product).where(Product.id == 3)))[0].category_id == 1
