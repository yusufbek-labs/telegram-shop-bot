"""i18n completeness: both languages must define the same keys with the same placeholders."""
import re

import pytest

from app.i18n import EN, RU, resolve_lang, t
from app.services.orders import PAYMENT_METHODS, STATUSES

PLACEHOLDER = re.compile(r"{(\w+)}")


def test_same_keys_in_both_languages():
    assert set(EN) - set(RU) == set(), "missing in RU"
    assert set(RU) - set(EN) == set(), "missing in EN"


@pytest.mark.parametrize("key", sorted(EN))
def test_placeholders_match_and_text_not_empty(key):
    assert EN[key].strip() and RU[key].strip()
    assert set(PLACEHOLDER.findall(EN[key])) == set(PLACEHOLDER.findall(RU[key]))


def test_every_status_and_payment_method_has_a_label():
    for key in [f"status_{s}" for s in STATUSES] + [f"payment_{m}" for m in PAYMENT_METHODS]:
        assert key in EN and key in RU


def test_russian_texts_are_actually_translated():
    cyrillic = sum(1 for v in RU.values() if re.search("[а-яА-Я]", v))
    assert cyrillic >= len(RU) * 0.95


@pytest.mark.parametrize("code,lang", [("ru", "ru"), ("ru-RU", "ru"), ("uk", "ru"), ("en", "en"),
                                       ("en-US", "en"), ("de", "en"), (None, "en"), ("", "en")])
def test_resolve_lang(code, lang):
    assert resolve_lang(code) == lang


def test_t_formats_and_falls_back_to_english():
    assert "Maple" in t("en", "welcome", shop="Maple")
    assert "Maple" in t("ru", "welcome", shop="Maple")
    assert t("xx", "cancelled") == EN["cancelled"]
