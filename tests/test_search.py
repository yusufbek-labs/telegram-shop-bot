"""Product search by name or category: handlers (real Dispatcher) and the matching service."""
import pytest
from sqlalchemy import select

from app.callbacks import Menu, ProductToggle
from app.db.models import Product
from app.i18n import EN, RU
from app.repositories import CatalogRepo
from app.services.catalog import normalize, search_products
from tests.conftest import ADMIN_ID, CUSTOMER_ID


async def _add_products(harness, *items):
    """items: (category_id, name) pairs."""
    async with harness.dp.workflow_data["sessionmaker"]() as s:
        for category_id, name in items:
            await CatalogRepo(s).add_product(
                category_id=category_id, name=name, description="d", price_cents=500, image_url=None
            )
        await s.commit()


def _card_names(harness, chat_id=CUSTOMER_ID):
    return [t.split("\n", 1)[0] for t in harness.texts_to(chat_id) if "💰" in t]


async def test_search_command_shows_matching_cards_and_footer(harness):
    await harness.say(CUSTOMER_ID, "/search green")
    texts = harness.texts_to(CUSTOMER_ID)
    assert "Search: green" in texts[0] and "Found 1" in texts[0]
    assert _card_names(harness) == ["<b>Alpine Green Tea, 100 g</b>"]
    assert "Alpine Green Tea" in texts[1] and "$12.50" in texts[1]
    footer = harness.sent_to(CUSTOMER_ID)[-1]
    assert footer.text == EN["search_footer"].format(query="green", count=1)
    labels = [b.text for row in footer.reply_markup.inline_keyboard for b in row]
    assert EN["btn_search_again"] in labels
    add_button = harness.sent_to(CUSTOMER_ID)[1].reply_markup.inline_keyboard[0][0]
    assert add_button.text == EN["btn_add"]


async def test_search_is_case_insensitive_and_needs_every_word(harness):
    await harness.say(CUSTOMER_ID, "/search ALPINE green")
    assert "Alpine Green Tea" in " ".join(harness.texts_to(CUSTOMER_ID))
    await harness.say(CUSTOMER_ID, "/search alpine candle")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["search_nothing"].format(query="alpine candle")


async def test_search_matches_cyrillic_names_in_any_case(harness):
    await _add_products(harness, (1, "Зелёный чай Алтай"), (1, "Чёрный чай с бергамотом"), (2, "Свеча Лаванда"))
    await harness.say(CUSTOMER_ID, "/search ЗЕЛЕНЫЙ")  # upper case, and е for ё
    shown = " ".join(harness.texts_to(CUSTOMER_ID))
    assert "Зелёный чай Алтай" in shown and "Чёрный" not in shown

    await harness.say(CUSTOMER_ID, "/search чАй")
    shown = " ".join(harness.texts_to(CUSTOMER_ID)[3:])
    assert "Зелёный чай Алтай" in shown and "Чёрный чай с бергамотом" in shown


async def test_search_matches_category_names_in_both_languages(harness):
    await harness.say(CUSTOMER_ID, "/search СВЕЧИ")  # the Russian name of "Candles"
    shown = " ".join(harness.texts_to(CUSTOMER_ID))
    assert "Pine Forest Candle" in shown and "Maple Morning Candle" in shown and "Travel Tin Candle" in shown
    assert "Alpine Green Tea" not in shown


async def test_search_nothing_found_offers_next_steps(harness):
    await harness.say(CUSTOMER_ID, "/search unicorn")
    reply = harness.sent_to(CUSTOMER_ID)[-1]
    assert reply.text == EN["search_nothing"].format(query="unicorn")
    labels = [b.text for row in reply.reply_markup.inline_keyboard for b in row]
    assert labels == [EN["btn_search_again"], EN["btn_catalog"], EN["btn_cart"]]
    assert len(harness.sent_to(CUSTOMER_ID)) == 1, "no header, cards or footer"


async def test_search_skips_hidden_products(harness):
    await harness.press(ADMIN_ID, ProductToggle(product_id=1))  # Alpine Green Tea off
    await harness.say(CUSTOMER_ID, "/search alpine")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["search_nothing"].format(query="alpine")


async def test_search_query_is_escaped_in_replies(harness):
    await harness.say(CUSTOMER_ID, "/search <b>x</b>")
    assert "&lt;b&gt;x&lt;/b&gt;" in harness.texts_to(CUSTOMER_ID)[-1]


async def test_menu_button_asks_for_a_query_then_searches(harness):
    await harness.say(CUSTOMER_ID, "/start")
    menu = harness.sent_to(CUSTOMER_ID)[-1].reply_markup.inline_keyboard
    assert Menu(action="search").pack() in [b.callback_data for row in menu for b in row]

    await harness.press(CUSTOMER_ID, Menu(action="search"))
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["search_prompt"]
    await harness.say(CUSTOMER_ID, "maple")
    assert "Maple Morning Candle" in " ".join(harness.texts_to(CUSTOMER_ID))

    await harness.say(CUSTOMER_ID, "maple")  # the query step is over: plain text is not a search any more
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["unknown_input"]


async def test_search_without_arguments_prompts_and_rejects_bad_queries(harness):
    await harness.say(CUSTOMER_ID, "/search")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["search_prompt"]
    await harness.say(CUSTOMER_ID, "a")
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["search_invalid"]
    await harness.say(CUSTOMER_ID, "x" * 51)
    assert harness.texts_to(CUSTOMER_ID)[-1] == EN["search_invalid"]
    await harness.say(CUSTOMER_ID, "linen")  # still in the query step
    assert "Linen Tea Towel" in " ".join(harness.texts_to(CUSTOMER_ID))


async def test_search_caps_the_number_of_cards(harness):
    await _add_products(harness, *[(3, f"Widget {n}") for n in range(12)])
    await harness.say(CUSTOMER_ID, "/search widget")
    texts = harness.texts_to(CUSTOMER_ID)
    assert "Found 12" in texts[0]
    assert len(_card_names(harness)) == 10
    assert texts[-1] == EN["search_footer_more"].format(query="widget", shown=10, count=12)


async def test_search_in_russian(harness):
    await harness.say(CUSTOMER_ID, "/search linen", lang="ru")
    assert "Поиск: linen" in harness.texts_to(CUSTOMER_ID)[0]
    await harness.say(CUSTOMER_ID, "/search ничегонет", lang="ru")
    assert harness.texts_to(CUSTOMER_ID)[-1] == RU["search_nothing"].format(query="ничегонет")


@pytest.mark.parametrize("text,folded", [("  Зелёный   ЧАЙ ", "зеленый чай"), ("Tea", "tea"), ("", "")])
def test_normalize(text, folded):
    assert normalize(text) == folded


async def test_search_products_service_returns_active_matches_in_catalog_order(seeded):
    async with seeded() as s:
        tea = await search_products(s, "tea")
        assert [p.id for p in tea] == [1, 2, 3, 7, 8, 9]  # the Tea category plus other names containing "tea"
        assert await search_products(s, "   ") == []
        product = (await s.scalars(select(Product).where(Product.id == 2))).one()
        product.is_active = False
        await s.flush()
        assert 2 not in [p.id for p in await search_products(s, "tea")]
