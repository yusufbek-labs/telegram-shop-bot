"""Public demo mode: the note, the owner's copy, automatic status change, limits and cleanup."""
import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app import demo
from app.callbacks import AddToCart, CartAct, Confirm, OrderStatusCb, Pay
from app.config import Settings
from app.db.models import Order, OrderItem, Product, User, utcnow
from app.i18n import EN, RU
from scripts.seed import seed
from tests.conftest import ADMIN_ID, CUSTOMER_ID, Harness
from tests.test_handlers import _db, _place_order
from tests.test_receipts import _to_receipt_step

OWNER_HEADER = "This is what the shop owner gets:"


@pytest.fixture(autouse=True)
def instant_sleep(monkeypatch):
    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(demo, "_sleep", no_wait)


def demo_harness(settings: Settings, seeded, **changes) -> Harness:
    return Harness(settings.model_copy(update={"demo_mode": True, "demo_status_seconds": 0, **changes}), seeded)


async def _count_orders(h) -> int:
    return len(await _db(h, select(Order)))


def test_demo_settings_default_to_off():
    s = Settings(_env_file=None)
    assert (s.demo_mode, s.demo_max_orders_per_day, s.demo_status_seconds) == (False, 5, 60)


# --- the note ----------------------------------------------------------------------------------------

async def test_start_shows_the_demo_note_in_both_languages(settings, seeded):
    h = demo_harness(settings, seeded)
    await h.say(CUSTOMER_ID, "/start")
    assert "This is a demo shop. Please don't enter real personal data." in h.texts_to(CUSTOMER_ID)[-1]
    await h.say(CUSTOMER_ID + 1, "/start", lang="ru")
    assert RU["demo_note"] in h.texts_to(CUSTOMER_ID + 1)[-1]


async def test_start_has_no_note_when_demo_mode_is_off(harness):
    await harness.say(CUSTOMER_ID, "/start")
    assert "demo shop" not in harness.texts_to(CUSTOMER_ID)[-1]


# --- what the owner gets -------------------------------------------------------------------------------

async def test_visitor_gets_a_copy_of_the_owner_card_with_inactive_buttons(settings, seeded):
    h = demo_harness(settings, seeded)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    copy = h.sent_to(CUSTOMER_ID)[-1]
    admin_card = h.sent_to(ADMIN_ID)[-1]
    assert copy.text == f"{OWNER_HEADER}\n\n{admin_card.text}"
    assert copy.reply_markup == admin_card.reply_markup
    assert OrderStatusCb(order_id=1, status="confirmed").pack() in [
        b.callback_data for row in copy.reply_markup.inline_keyboard for b in row
    ]

    await h.press(CUSTOMER_ID, OrderStatusCb(order_id=1, status="confirmed"))
    assert EN["demo_buttons_inactive"] in h.alerts()
    assert (await _db(h, select(Order)))[0].status == "new"


async def test_visitors_get_no_admin_rights(settings, seeded):
    h = demo_harness(settings, seeded)
    await h.say(CUSTOMER_ID, "/orders")
    assert EN["admin_orders_title"] not in h.texts_to(CUSTOMER_ID)


async def test_owner_copy_carries_the_receipt(settings, seeded):
    h = demo_harness(settings, seeded)
    await h.say(ADMIN_ID, "/start")
    await _to_receipt_step(h)
    await h.send_photo(CUSTOMER_ID, "AgACphoto")
    await h.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))
    copy = h.sent_to(CUSTOMER_ID)[-1]
    assert type(copy).__name__ == "SendPhoto" and copy.photo == "AgACphoto"
    assert copy.caption.startswith(OWNER_HEADER)


async def test_without_demo_mode_the_customer_gets_no_copy(harness):
    await harness.say(ADMIN_ID, "/start")
    await _place_order(harness)
    assert not any("New order" in text for text in harness.texts_to(CUSTOMER_ID))
    assert demo._tasks == set()


# --- automatic status ----------------------------------------------------------------------------------

async def test_order_moves_to_the_next_status_and_the_visitor_is_told(settings, seeded):
    h = demo_harness(settings, seeded, demo_status_seconds=60)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    assert len(demo._tasks) == 1
    await demo.drain()
    assert (await _db(h, select(Order)))[0].status == "confirmed"
    assert h.texts_to(CUSTOMER_ID)[-1] == EN["order_status_update"].format(id=1, status=EN["status_confirmed"])


async def test_auto_status_leaves_an_order_the_owner_already_moved(settings, seeded, monkeypatch):
    gate = asyncio.Event()  # the minute has not passed yet while the owner acts
    monkeypatch.setattr(demo, "_sleep", lambda _seconds: gate.wait())
    h = demo_harness(settings, seeded, demo_status_seconds=60)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    await h.press(ADMIN_ID, OrderStatusCb(order_id=1, status="cancelled"))
    sent = len(h.sent_to(CUSTOMER_ID))
    gate.set()
    await demo.drain()
    assert (await _db(h, select(Order)))[0].status == "cancelled"
    assert len(h.sent_to(CUSTOMER_ID)) == sent


async def test_auto_status_can_be_turned_off(settings, seeded):
    h = demo_harness(settings, seeded, demo_status_seconds=0)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    assert demo._tasks == set()
    assert (await _db(h, select(Order)))[0].status == "new"


async def test_advance_never_cancels_and_stops_at_final_statuses(settings, seeded):
    h = demo_harness(settings, seeded)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    sm = h.dp.workflow_data["sessionmaker"]
    for expected in ("new", "confirmed", "shipped"):
        assert await demo.advance_order(h.bot, sm, 1, expected) is True
    assert (await _db(h, select(Order)))[0].status == "delivered"
    assert await demo.advance_order(h.bot, sm, 1, "delivered") is False


# --- limits ---------------------------------------------------------------------------------------------

async def test_visitor_is_limited_to_a_few_orders_a_day(settings, seeded):
    h = demo_harness(settings, seeded, demo_max_orders_per_day=2)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    await _place_order(h)
    assert await _count_orders(h) == 2
    await _place_order(h)  # the third attempt stops at the Checkout button
    assert EN["demo_limit"].format(n=2) in h.alerts()
    assert await _count_orders(h) == 2


async def test_limit_counts_a_rolling_day_and_spares_the_owner(settings, seeded):
    h = demo_harness(settings, seeded, demo_max_orders_per_day=1)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    sm = h.dp.workflow_data["sessionmaker"]
    s = h.dp.workflow_data["settings"]
    async with sm() as session:
        assert await demo.limit_reached(session, s, CUSTOMER_ID) is True
        assert await demo.limit_reached(session, s, ADMIN_ID) is False
        order = await session.get(Order, 1)
        order.created_at = utcnow() - timedelta(hours=25)
        await session.commit()
        assert await demo.limit_reached(session, s, CUSTOMER_ID) is False
        assert await demo.limit_reached(session, s.model_copy(update={"demo_mode": False}), CUSTOMER_ID) is False


async def test_confirming_after_the_limit_was_reached_places_no_order(settings, seeded):
    h = demo_harness(settings, seeded, demo_max_orders_per_day=1)
    await h.say(ADMIN_ID, "/start")
    await h.press(CUSTOMER_ID, AddToCart(product_id=1))
    await h.press(CUSTOMER_ID, CartAct(action="checkout"))
    await h.say(CUSTOMER_ID, "Ann Lee")
    await h.say(CUSTOMER_ID, "+1 555 123 4567")
    await h.say(CUSTOMER_ID, "12 Birch Street, Springfield")
    await h.press(CUSTOMER_ID, Pay(method="cash"))
    async with h.dp.workflow_data["sessionmaker"]() as session:  # an order from another chat window gets in first
        session.add(Order(user_id=CUSTOMER_ID, customer_name="Ann Lee", phone="+15551234567", address="Somewhere 1",
                          payment_method="cash", total_cents=100))
        await session.commit()
    await h.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))
    assert await _count_orders(h) == 1
    assert EN["demo_limit"].format(n=1) in h.last_reply_text()


# --- cleanup -------------------------------------------------------------------------------------------

async def test_old_demo_orders_are_deleted_with_their_lines(settings, seeded):
    h = demo_harness(settings, seeded)
    await h.say(ADMIN_ID, "/start")
    await _place_order(h)
    await _place_order(h)
    sm = h.dp.workflow_data["sessionmaker"]
    async with sm() as session:
        old = await session.get(Order, 1)
        old.created_at = utcnow() - timedelta(days=8)
        await session.commit()
    assert await demo.purge_old_orders(sm) == 1
    assert [o.id for o in await _db(h, select(Order))] == [2]
    async with sm() as session:
        assert await session.scalar(select(func.count(OrderItem.id))) == 1
        assert await session.get(User, CUSTOMER_ID) is not None
    assert await demo.purge_old_orders(sm) == 0


# --- seed ----------------------------------------------------------------------------------------------

async def test_demo_seed_gives_every_product_a_public_photo(sessionmaker):
    assert await seed(sessionmaker, demo=True) == 9
    async with sessionmaker() as session:
        products = list(await session.scalars(select(Product)))
    assert all(p.image_url.startswith("https://placehold.co/") for p in products)
    assert "Alpine+Green+Tea%2C+100+g" in next(p for p in products if p.name.startswith("Alpine")).image_url


async def test_plain_seed_keeps_photos_as_before(sessionmaker):
    await seed(sessionmaker)
    async with sessionmaker() as session:
        products = list(await session.scalars(select(Product)))
    assert sum(p.image_url is not None for p in products) == 2
