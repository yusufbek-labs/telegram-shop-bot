"""Handler tests: real Dispatcher + real handlers, with Telegram replaced by a recording fake session."""
import asyncio

from sqlalchemy import select

from app.callbacks import (
    AddToCart,
    Cat,
    CartAct,
    Confirm,
    EditField,
    Lang,
    Menu,
    OrderStatusCb,
    Pay,
    PickCategory,
    ProductEdit,
    ProductToggle,
)
from app.db.models import Order, Product, User
from app.handlers import admin_misc
from app.i18n import EN, RU
from tests.conftest import ADMIN_ID, CUSTOMER_ID


async def _db(harness, stmt):
    async with harness.dp.workflow_data["sessionmaker"]() as s:
        return list(await s.scalars(stmt))


async def _place_order(h):
    """Customer buys 2 x product 1 through the real button flow."""
    await h.press(CUSTOMER_ID, Menu(action="catalog"))
    await h.press(CUSTOMER_ID, Cat(id=1))
    await h.press(CUSTOMER_ID, AddToCart(product_id=1))
    await h.press(CUSTOMER_ID, AddToCart(product_id=1))
    await h.press(CUSTOMER_ID, Menu(action="cart"))
    await h.press(CUSTOMER_ID, CartAct(action="checkout"))
    await h.say(CUSTOMER_ID, "Ann Lee")
    await h.say(CUSTOMER_ID, "+1 555 123 4567")
    await h.say(CUSTOMER_ID, "12 Birch Street, Springfield")
    await h.press(CUSTOMER_ID, Pay(method="cash"))
    await h.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))


async def test_start_detects_russian_and_stores_language(harness):
    await harness.say(CUSTOMER_ID, "/start", lang="ru-RU")
    assert "Добро пожаловать" in harness.texts_to(CUSTOMER_ID)[0]
    user = (await _db(harness, select(User).where(User.id == CUSTOMER_ID)))[0]
    assert user.language == "ru"
    markup = harness.sent_to(CUSTOMER_ID)[0].reply_markup
    assert len(markup.inline_keyboard) >= 2


async def test_start_defaults_to_english_and_language_switch(harness):
    await harness.say(CUSTOMER_ID, "/start", lang="de")
    assert "Welcome" in harness.texts_to(CUSTOMER_ID)[0]
    await harness.say(CUSTOMER_ID, "/language")
    await harness.press(CUSTOMER_ID, Lang(code="ru"))
    assert harness.last_reply_text().startswith(RU["language_set"])
    await harness.say(CUSTOMER_ID, "/help")
    assert harness.texts_to(CUSTOMER_ID)[-1] == RU["help"]


async def test_full_purchase_flow_and_admin_notification(harness):
    await harness.say(ADMIN_ID, "/start")  # admins must have started the bot to be reachable
    await _place_order(harness)

    orders = await _db(harness, select(Order))
    assert len(orders) == 1
    order = orders[0]
    assert (order.total_cents, order.status, order.payment_method) == (2500, "new", "cash")
    assert order.phone == "+15551234567" and order.customer_name == "Ann Lee"

    assert "#1" in harness.last_reply_text()
    admin_msgs = [c for c in harness.sent_to(ADMIN_ID) if "New order" in c.text]
    assert len(admin_msgs) == 1
    buttons = [b.text for row in admin_msgs[0].reply_markup.inline_keyboard for b in row]
    assert len(buttons) == 2  # from "new" only confirmed / cancelled are offered
    assert "Alpine Green Tea" in admin_msgs[0].text


async def test_admin_status_buttons_enforce_rules_and_notify_customer(harness):
    await harness.say(ADMIN_ID, "/start")
    await _place_order(harness)

    # forged jump new -> delivered is refused
    await harness.press(ADMIN_ID, OrderStatusCb(order_id=1, status="delivered"))
    assert (await _db(harness, select(Order)))[0].status == "new"
    assert EN["status_not_allowed"] in harness.alerts()

    # a customer pressing an admin button is refused
    await harness.press(CUSTOMER_ID, OrderStatusCb(order_id=1, status="confirmed"))
    assert (await _db(harness, select(Order)))[0].status == "new"
    assert EN["no_permission"] in harness.alerts()

    # legit change goes through and the customer is told
    await harness.press(ADMIN_ID, OrderStatusCb(order_id=1, status="confirmed"))
    assert (await _db(harness, select(Order)))[0].status == "confirmed"
    assert any("Confirmed" in text for text in harness.texts_to(CUSTOMER_ID))
    assert harness.edits(), "admin card should be edited in place"


async def test_cart_controls_and_empty_checkout_guard(harness):
    await harness.press(CUSTOMER_ID, CartAct(action="checkout"))
    assert EN["cart_empty"] in harness.alerts()
    await harness.press(CUSTOMER_ID, AddToCart(product_id=2))
    await harness.press(CUSTOMER_ID, CartAct(action="inc", product_id=2))
    await harness.press(CUSTOMER_ID, Menu(action="cart"))
    assert "× 2 = $28.00" in harness.last_reply_text()
    await harness.press(CUSTOMER_ID, CartAct(action="clear"))
    assert EN["cart_empty"] in harness.last_reply_text()


async def test_checkout_validation_keeps_state_and_unknown_input_is_handled(harness):
    await harness.press(CUSTOMER_ID, AddToCart(product_id=1))
    await harness.press(CUSTOMER_ID, CartAct(action="checkout"))
    await harness.say(CUSTOMER_ID, "x")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["invalid_name"]
    await harness.say(CUSTOMER_ID, "Bob")
    await harness.say(CUSTOMER_ID, "not-a-phone")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["invalid_phone"]
    await harness.say(CUSTOMER_ID, "/cancel")
    assert EN["cancelled"] in harness.texts_to(CUSTOMER_ID)
    assert await _db(harness, select(Order)) == []


async def test_unknown_input_never_crashes(harness):
    await harness.say(CUSTOMER_ID, "blah blah")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["unknown_input"]
    await harness.say(CUSTOMER_ID, "/nonsense")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["unknown_command"]
    await harness.say(CUSTOMER_ID, "/stats")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["no_permission"]
    await harness.press(CUSTOMER_ID, ProductToggle(product_id=1))
    assert EN["stale_button"] in harness.alerts()
    assert all(p.is_active for p in await _db(harness, select(Product)))


async def test_admin_toggle_hides_product_from_catalog(harness):
    await harness.say(ADMIN_ID, "/products")
    assert "Products" in harness.texts_to(ADMIN_ID)[-1]
    await harness.press(ADMIN_ID, ProductToggle(product_id=1))
    assert (await _db(harness, select(Product).where(Product.id == 1)))[0].is_active is False
    await harness.press(CUSTOMER_ID, Cat(id=1))
    shown = " ".join(harness.texts_to(CUSTOMER_ID))
    assert "Alpine Green Tea" not in shown and "Smoked Black Tea" in shown


async def test_add_product_fsm(harness):
    await harness.say(ADMIN_ID, "/add_product")
    await harness.press(ADMIN_ID, PickCategory(category_id=2))
    await harness.say(ADMIN_ID, "Beeswax Candle")
    await harness.say(ADMIN_ID, "abc")  # invalid price keeps the step
    assert harness.texts_to(ADMIN_ID)[-1] == EN["invalid_price"]
    await harness.say(ADMIN_ID, "15,50")
    await harness.say(ADMIN_ID, "Natural beeswax, honey scent.")
    await harness.say(ADMIN_ID, "-")
    await harness.press(ADMIN_ID, Confirm(ctx="product", ok=True))
    created = (await _db(harness, select(Product).where(Product.name == "Beeswax Candle")))[0]
    assert (created.price_cents, created.category_id, created.image_url, created.is_active) == (1550, 2, None, True)


async def test_edit_product_fsm(harness):
    await harness.say(ADMIN_ID, "/edit_product")
    await harness.press(ADMIN_ID, ProductEdit(product_id=3))
    await harness.press(ADMIN_ID, EditField(field="price"))
    await harness.say(ADMIN_ID, "13")
    product = (await _db(harness, select(Product).where(Product.id == 3)))[0]
    assert product.price_cents == 1300


async def test_stats_command_for_admin(harness):
    await _place_order(harness)
    await harness.say(ADMIN_ID, "/stats")
    text = harness.texts_to(ADMIN_ID)[-1]
    assert "Today: 1 orders, $25.00" in text and "Last 7 days: 1 orders, $25.00" in text


async def test_broadcast_requires_confirmation_and_reports(harness):
    await harness.say(CUSTOMER_ID, "/start")
    await harness.say(ADMIN_ID, "/start")
    await harness.say(ADMIN_ID, "/broadcast")
    await harness.say(ADMIN_ID, "Spring sale <b>today</b>")
    assert "Preview" in harness.texts_to(ADMIN_ID)[-1]
    assert not any("Spring sale" in x for x in harness.texts_to(CUSTOMER_ID)), "nothing sent before confirm"

    await harness.press(ADMIN_ID, Confirm(ctx="broadcast", ok=True))
    await asyncio.gather(*admin_misc._background)
    assert any("Spring sale" in x for x in harness.texts_to(CUSTOMER_ID))
    assert "sent 2" in harness.texts_to(ADMIN_ID)[-1]


async def test_broadcast_cancel_sends_nothing(harness):
    await harness.say(CUSTOMER_ID, "/start")
    await harness.say(ADMIN_ID, "/broadcast")
    await harness.say(ADMIN_ID, "Hello all")
    await harness.press(ADMIN_ID, Confirm(ctx="broadcast", ok=False))
    assert not any("Hello all" in x for x in harness.texts_to(CUSTOMER_ID))
    assert EN["broadcast_cancelled"] in harness.last_reply_text()
