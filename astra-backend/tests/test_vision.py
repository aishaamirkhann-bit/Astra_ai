import base64
import json
import urllib.error

from app.services import vision


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        _ = exc_type, exc_value, traceback
        return None

    def read(self) -> bytes:
        return self._body


def _configure_groq(monkeypatch) -> None:
    monkeypatch.setattr(vision.settings, "VISION_PROVIDER", "groq")
    monkeypatch.setattr(vision.settings, "VISION_API_KEY", "test-vision-key")
    monkeypatch.setattr(vision.settings, "VISION_MODEL", "test/vision-model")


def test_chat_vision_posts_image_and_prompt_to_groq(monkeypatch, valid_png_bytes: bytes) -> None:
    _configure_groq(monkeypatch)
    requests = []

    def fake_urlopen(request, *, timeout: float):
        requests.append((request, timeout))
        return _FakeResponse({
            "choices": [{"message": {"content": "A bright room with neutral walls."}}],
        })

    monkeypatch.setattr(vision.urllib.request, "urlopen", fake_urlopen)
    result = vision.describe_image_for_chat(
        valid_png_bytes,
        "image/png",
        "How can I style this room?",
    )

    assert result.status == "analyzed"
    assert result.answer == "A bright room with neutral walls."
    request, timeout = requests[0]
    assert request.full_url == vision.GROQ_CHAT_URL
    assert request.get_header("Authorization") == "Bearer test-vision-key"
    assert timeout == vision.settings.VISION_TIMEOUT_SECONDS
    payload = json.loads(request.data)
    assert payload["model"] == "test/vision-model"
    content = payload["messages"][0]["content"]
    assert "How can I style this room?" in content[0]["text"]
    image_url = content[1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert base64.b64decode(image_url.split(",", maxsplit=1)[1]) == valid_png_bytes


def test_chat_vision_returns_not_configured_without_provider_or_key(monkeypatch) -> None:
    monkeypatch.setattr(vision.settings, "VISION_PROVIDER", "")
    monkeypatch.setattr(vision.settings, "VISION_API_KEY", "")
    monkeypatch.setattr(vision.settings, "GROQ_API_KEY", "")

    def unexpected_request(request, *, timeout: float):
        assert request is not None and timeout > 0
        raise AssertionError("provider should not be called without configuration")

    monkeypatch.setattr(vision.urllib.request, "urlopen", unexpected_request)
    result = vision.describe_image_for_chat(b"sample-image", "image/jpeg", "")

    assert result.status == "not_configured"
    assert result.answer is None


def test_chat_vision_uses_groq_key_when_dedicated_vision_key_is_missing(monkeypatch, valid_png_bytes: bytes) -> None:
    monkeypatch.setattr(vision.settings, "VISION_PROVIDER", "")
    monkeypatch.setattr(vision.settings, "VISION_API_KEY", "")
    monkeypatch.setattr(vision.settings, "GROQ_API_KEY", "test-groq-key")
    requests = []

    def fake_urlopen(request, *, timeout: float):
        requests.append(request)
        assert timeout > 0
        return _FakeResponse({
            "choices": [{"message": {"content": "A red leather handbag."}}],
        })

    monkeypatch.setattr(vision.urllib.request, "urlopen", fake_urlopen)
    result = vision.describe_image_for_chat(valid_png_bytes, "image/png", "Describe this.")

    assert result.status == "analyzed"
    assert requests[0].get_header("Authorization") == "Bearer test-groq-key"


def test_dedicated_vision_key_takes_precedence_over_general_groq_key(monkeypatch, valid_png_bytes: bytes) -> None:
    _configure_groq(monkeypatch)
    monkeypatch.setattr(vision.settings, "GROQ_API_KEY", "fallback-groq-key")
    requests = []

    def fake_urlopen(request, *, timeout: float):
        requests.append(request)
        assert timeout > 0
        return _FakeResponse({
            "choices": [{"message": {"content": "A blue ceramic vase."}}],
        })

    monkeypatch.setattr(vision.urllib.request, "urlopen", fake_urlopen)
    vision.describe_image_for_chat(valid_png_bytes, "image/png", "Describe this.")

    assert requests[0].get_header("Authorization") == "Bearer test-vision-key"


def test_chat_vision_returns_provider_error_on_http_failure(monkeypatch, valid_png_bytes: bytes) -> None:
    _configure_groq(monkeypatch)

    def failed_request(request, *, timeout: float):
        assert request.full_url == vision.GROQ_CHAT_URL
        assert timeout > 0
        raise urllib.error.HTTPError(
            vision.GROQ_CHAT_URL,
            503,
            "service unavailable",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(vision.urllib.request, "urlopen", failed_request)
    result = vision.describe_image_for_chat(valid_png_bytes, "image/png", "")

    assert result.status == "provider_error"
    assert result.answer is None


def test_chat_vision_returns_provider_error_for_malformed_response(monkeypatch, valid_png_bytes: bytes) -> None:
    _configure_groq(monkeypatch)

    def malformed_response(request, *, timeout: float):
        assert request.full_url == vision.GROQ_CHAT_URL
        assert timeout > 0
        return _FakeResponse({"choices": []})

    monkeypatch.setattr(
        vision.urllib.request,
        "urlopen",
        malformed_response,
    )

    result = vision.describe_image_for_chat(valid_png_bytes, "image/png", "")

    assert result.status == "provider_error"
    assert result.answer is None


def test_explore_vision_uses_shared_groq_request_and_returns_labels(monkeypatch, valid_png_bytes: bytes) -> None:
    _configure_groq(monkeypatch)

    def successful_response(request, *, timeout: float):
        assert request.full_url == vision.GROQ_CHAT_URL
        assert timeout > 0
        return _FakeResponse({
            "choices": [{"message": {"content": '{"category":"","color":"","style":"","pattern":"","keywords":["wireless","earbuds"]}'}}],
        })

    monkeypatch.setattr(
        vision.urllib.request,
        "urlopen",
        successful_response,
    )

    result = vision.analyze_image(valid_png_bytes, "product.png")

    assert result is not None
    assert result.query == "wireless earbuds"
    assert result.labels == ["wireless", "earbuds"]
    assert result.provider == "groq"
