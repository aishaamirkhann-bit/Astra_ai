import pytest

from app.services.shopping_nlu import detect_greeting, greeting_response, product_matches_response


@pytest.mark.parametrize(
    ("text", "locale", "expected"),
    [
        ("salaam", "roman_urdu", "Walaikum Assalam"),
        ("hi", "fa-IR", "\u0633\u0644\u0627\u0645"),
        ("hello", "zh-CN", "\u4f60\u597d"),
        ("\u0627\u0644\u0633\u0644\u0627\u0645 \u0639\u0644\u064a\u0643\u0645", "ar-AE", "\u0648\u0639\u0644\u064a\u0643\u0645"),
        ("\u0645\u0631\u062d\u0628\u0627", "fa", "\u0633\u0644\u0627\u0645"),
        ("\u0a38\u0a24 \u0a38\u0a4d\u0a30\u0a40 \u0a05\u0a15\u0a3e\u0a32", "pa", "Sat sri akal"),
        ("salaam", "ur", "\u0648\u0639\u0644\u06cc\u06a9\u0645"),
        ("salaam", "ps", "\u0648\u0627\u0644\u064a\u06a9\u0645"),
        ("salaam", "sd", "\u0648\u0639\u0644\u064a\u06aa\u0645"),
    ],
)
def test_greeting_is_recognized_and_answered_in_active_locale(text: str, locale: str, expected: str) -> None:
    assert detect_greeting(text)
    assert expected in greeting_response(locale)


def test_product_recommendation_intro_uses_active_locale() -> None:
    assert "Mujhe" in product_matches_response("roman_urdu")
    assert "\u0686" in product_matches_response("fa-IR")
    assert "\u627e" in product_matches_response("zh-CN")

