"""Bank transfer checkout with a receipt upload, and how the admin gets it."""
import pytest
from sqlalchemy import select

from app.callbacks import AddToCart, CartAct, Confirm, Menu, OrderOpen, OrderReceipt, OrderStatusCb, Pay
from app.db.models import Order, User
from app.handlers.common import notify_admins_new_order
from app.i18n import EN, RU
from app.repositories import OrderRepo
from app.services.cart import CartService
from app.services.orders import CheckoutData, OrderService, ReceiptRequired
from tests.conftest import ADMIN_ID, CUSTOMER_ID, Harness
from tests.test_handlers import _db


async def _to_payment_step(h, lang="en"):
    await h.say(ADMIN_ID, "/start")  # admins must have started the bot to be reachable
    await h.press(CUSTOMER_ID, AddToCart(product_id=1), lang=lang)
    await h.press(CUSTOMER_ID, CartAct(action="checkout"), lang=lang)
    await h.say(CUSTOMER_ID, "Ann Lee", lang=lang)
    await h.say(CUSTOMER_ID, "+1 555 123 4567", lang=lang)
    await h.say(CUSTOMER_ID, "12 Birch Street, Springfield", lang=lang)


async def _to_receipt_step(h, lang="en"):
    await _to_payment_step(h, lang)
    await h.press(CUSTOMER_ID, Pay(method="transfer"), lang=lang)


def _buttons(message):
    return [b for row in message.reply_markup.inline_keyboard for b in row]


def _without_transfer(settings, seeded) -> Harness:
    return Harness(settings.model_copy(update={"payment_details": ""}), seeded)


async def test_payment_step_offers_transfer_only_when_details_are_configured(harness, settings, seeded):
    await _to_payment_step(harness)
    methods = [b.callback_data for b in _buttons(harness.sent_to(CUSTOMER_ID)[-1])]
    assert methods == [Pay(method=m).pack() for m in ("cash", "card", "transfer")]

    plain = _without_transfer(settings, seeded)
    await _to_payment_step(plain)
    methods = [b.callback_data for b in _buttons(plain.sent_to(CUSTOMER_ID)[-1])]
    assert methods == [Pay(method=m).pack() for m in ("cash", "card")]


async def test_transfer_button_pressed_after_the_option_was_switched_off_is_refused(settings, seeded):
    plain = _without_transfer(settings, seeded)
    await _to_payment_step(plain)
    await plain.press(CUSTOMER_ID, Pay(method="transfer"))
    assert EN["stale_button"] in plain.alerts()
    assert await _db(plain, select(Order)) == []


async def test_transfer_shows_bank_details_and_amount_then_waits_for_a_receipt(harness):
    await _to_receipt_step(harness)
    text = harness.last_reply_text()
    assert "Example Bank\nIBAN: DE00 0000 0000 0000 00" in text and "$12.50" in text
    assert await _db(harness, select(Order)) == []


async def test_receipt_as_photo_is_stored_with_the_largest_size(harness):
    await _to_receipt_step(harness)
    await harness.send_photo(CUSTOMER_ID, "AgACphoto")
    assert "Receipt: attached" in harness.last_reply_text()
    assert "Bank transfer" in harness.last_reply_text()
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))

    order = (await _db(harness, select(Order)))[0]
    assert (order.payment_method, order.receipt_file_id, order.receipt_type) == ("transfer", "AgACphoto", "photo")


async def test_receipt_as_pdf_document_is_stored(harness):
    await _to_receipt_step(harness)
    await harness.send_document(CUSTOMER_ID, "BQACdoc", mime="application/pdf")
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))

    order = (await _db(harness, select(Order)))[0]
    assert (order.receipt_file_id, order.receipt_type) == ("BQACdoc", "document")


async def test_receipt_as_image_file_is_accepted_but_other_files_are_not(harness):
    await _to_receipt_step(harness)
    await harness.send_document(CUSTOMER_ID, "zip-id", mime="application/zip")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["receipt_invalid"]
    await harness.send_document(CUSTOMER_ID, "png-id", mime="image/png")
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))
    assert (await _db(harness, select(Order)))[0].receipt_file_id == "png-id"


async def test_wrong_message_type_at_receipt_step_keeps_the_step(harness):
    await _to_receipt_step(harness)
    await harness.say(CUSTOMER_ID, "I paid, trust me")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["receipt_invalid"]
    await harness.say(CUSTOMER_ID, "/nonsense")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["unknown_command"]
    assert await _db(harness, select(Order)) == []

    await harness.send_photo(CUSTOMER_ID)  # still waiting for the receipt
    assert "Receipt: attached" in harness.last_reply_text()


async def test_cancel_at_receipt_step_places_no_order_and_keeps_the_cart(harness):
    await _to_receipt_step(harness)
    await harness.say(CUSTOMER_ID, "/cancel")
    assert EN["cancelled"] in harness.texts_to(CUSTOMER_ID)
    assert await _db(harness, select(Order)) == []
    await harness.send_photo(CUSTOMER_ID)  # no longer in the checkout
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["unknown_input"]
    await harness.press(CUSTOMER_ID, Menu(action="cart"))
    assert "Alpine Green Tea" in harness.last_reply_text()


async def test_cash_checkout_has_no_receipt_step_and_a_plain_admin_message(harness):
    await _to_payment_step(harness)
    await harness.press(CUSTOMER_ID, Pay(method="cash"))
    assert "Receipt" not in harness.last_reply_text()
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))
    order = (await _db(harness, select(Order)))[0]
    assert (order.receipt_file_id, order.receipt_type) == (None, None)

    sent = harness.sent_to(ADMIN_ID)[-1]
    assert type(sent).__name__ == "SendMessage" and "New order" in sent.text
    assert EN["btn_receipt"] not in [b.text for b in _buttons(sent)]


async def test_admin_notification_carries_the_photo_receipt_with_status_buttons(harness):
    await _to_receipt_step(harness)
    await harness.send_photo(CUSTOMER_ID, "AgACphoto")
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))

    sent = harness.sent_to(ADMIN_ID)[-1]
    assert type(sent).__name__ == "SendPhoto" and sent.photo == "AgACphoto"
    assert "New order #1" in sent.caption and "Alpine Green Tea" in sent.caption
    assert "Receipt: attached" in sent.caption and "Ann Lee" in sent.caption
    labels = [b.text for b in _buttons(sent)]
    assert labels == [EN["status_confirmed"], EN["status_cancelled"], EN["btn_receipt"]]


async def test_admin_notification_carries_the_pdf_receipt(harness):
    await _to_receipt_step(harness)
    await harness.send_document(CUSTOMER_ID, "BQACdoc")
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))

    sent = harness.sent_to(ADMIN_ID)[-1]
    assert type(sent).__name__ == "SendDocument" and sent.document == "BQACdoc"
    assert "New order #1" in sent.caption
    assert EN["status_confirmed"] in [b.text for b in _buttons(sent)]


async def test_long_order_summary_is_sent_as_text_with_the_receipt_underneath(harness):
    await _to_receipt_step(harness)
    await harness.send_photo(CUSTOMER_ID, "AgACphoto")
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))
    harness.session.calls.clear()

    async with harness.dp.workflow_data["sessionmaker"]() as s:
        order = await OrderRepo(s).get(1)
        order.address = "x" * 1100
        await notify_admins_new_order(harness.bot, s, harness.dp.workflow_data["settings"], order)

    text, receipt = harness.sent_to(ADMIN_ID)
    assert type(text).__name__ == "SendMessage" and len(text.text) > 1024
    assert EN["status_confirmed"] in [b.text for b in _buttons(text)]
    assert type(receipt).__name__ == "SendPhoto" and receipt.photo == "AgACphoto"
    assert receipt.caption == EN["receipt_caption"].format(id=1) and receipt.reply_to_message_id is not None


async def test_admin_can_open_the_receipt_from_the_order_card(harness):
    await _to_receipt_step(harness)
    await harness.send_document(CUSTOMER_ID, "BQACdoc")
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))

    await harness.press(ADMIN_ID, OrderOpen(order_id=1))
    card = harness.edits()[-1]
    assert "Receipt: attached" in card.text
    assert EN["btn_receipt"] in [b.text for b in _buttons(card)]

    await harness.press(ADMIN_ID, OrderReceipt(order_id=1))
    sent = harness.sent_to(ADMIN_ID)[-1]
    assert type(sent).__name__ == "SendDocument" and sent.document == "BQACdoc"
    assert sent.caption == EN["receipt_caption"].format(id=1)


async def test_receipt_button_is_refused_for_customers_and_for_orders_without_one(harness):
    await _to_payment_step(harness)
    await harness.press(CUSTOMER_ID, Pay(method="cash"))
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))

    await harness.press(ADMIN_ID, OrderReceipt(order_id=1))
    assert EN["receipt_missing"] in harness.alerts()
    await harness.press(ADMIN_ID, OrderReceipt(order_id=99))
    assert EN["order_not_found"] in harness.alerts()
    await harness.press(CUSTOMER_ID, OrderReceipt(order_id=1))
    assert EN["stale_button"] in harness.alerts()


async def test_status_buttons_on_the_receipt_message_edit_its_caption(harness):
    await _to_receipt_step(harness)
    await harness.send_photo(CUSTOMER_ID)
    await harness.press(CUSTOMER_ID, Confirm(ctx="checkout", ok=True))

    text_edits = len(harness.edits())
    await harness.press(ADMIN_ID, OrderStatusCb(order_id=1, status="confirmed"), on_photo=True)
    assert (await _db(harness, select(Order)))[0].status == "confirmed"
    [edit] = harness.caption_edits()
    assert "Confirmed" in edit.caption and "Receipt: attached" in edit.caption
    assert len(harness.edits()) == text_edits, "a photo message has no text to edit"
    assert any("Confirmed" in text for text in harness.texts_to(CUSTOMER_ID))


async def test_receipt_step_in_russian(harness):
    await _to_receipt_step(harness, lang="ru")
    assert "Оплата банковским переводом" in harness.last_reply_text()
    await harness.say(CUSTOMER_ID, "оплатил", lang="ru")
    assert harness.texts_to(CUSTOMER_ID)[-1] == RU["receipt_invalid"]
    await harness.send_photo(CUSTOMER_ID, lang="ru")
    assert "Квитанция: прикреплена" in harness.last_reply_text()


@pytest.fixture
async def session(seeded):
    async with seeded() as s:
        s.add(User(id=7, full_name="Buyer", language="en"))
        await s.flush()
        yield s


async def test_service_requires_a_receipt_for_transfer_orders(session):
    await CartService(session).add(7, 1)
    service = OrderService(session)
    with pytest.raises(ReceiptRequired):
        await service.checkout(7, CheckoutData("Ann Lee", "+15551234567", "12 Birch Street", "transfer"))
    with pytest.raises(ValueError):
        await service.checkout(7, CheckoutData("Ann Lee", "+15551234567", "12 Birch Street", "transfer", "f", "voice"))
    order = await service.checkout(7, CheckoutData("Ann Lee", "+15551234567", "12 Birch Street", "transfer", "f", "photo"))
    assert (order.receipt_file_id, order.receipt_type) == ("f", "photo")
