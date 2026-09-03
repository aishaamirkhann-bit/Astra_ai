"""Coverage for the /voice router: MIME rejection, provider-unconfigured
fallback, mocked-provider success, for both /voice/transcribe and /voice/synthesize."""
from fastapi.testclient import TestClient

from app.main import app


def _login(email: str = "aisha@astra.ai") -> TestClient:
    anonymous = TestClient(app)
    challenge = anonymous.post("/api/v1/auth/login", json={"email": email, "password": "demo1234"})
    assert challenge.status_code == 200, challenge.text
    verified = anonymous.post(
        "/api/v1/auth/verify-otp",
        json={"otp_token": challenge.json()["otp_token"], "code": "123456"},
    )
    assert verified.status_code == 200, verified.text
    return TestClient(app, headers={"Authorization": f"Bearer {verified.json()['access_token']}"})


def test_transcribe_requires_auth() -> None:
    anonymous = TestClient(app)
    response = anonymous.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("clip.webm", b"fake-audio", "audio/webm")},
    )
    assert response.status_code == 401


def test_transcribe_rejects_unsupported_mime() -> None:
    client = _login()
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("clip.txt", b"not-audio", "text/plain")},
    )
    assert response.status_code == 415


def test_transcribe_falls_back_when_provider_unconfigured() -> None:
    """STT_PROVIDER is unset in tests -> keep the same deterministic string the
    rest of the app already relies on (see services/explore.py)."""
    client = _login()
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("clip.webm", b"fake-audio", "audio/webm")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "gaming laptop 200k ke under"
    assert body["provider"] == "browser-fallback"


def test_transcribe_uses_configured_provider(monkeypatch) -> None:
    from app.api.v1.endpoints import voice as voice_endpoint

    monkeypatch.setattr(voice_endpoint, "transcribe", lambda audio_bytes, mime: "mocked transcript")
    client = _login()
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"audio": ("clip.webm", b"fake-audio", "audio/webm")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "mocked transcript"
    assert body["provider"] == "server-stt"


def test_synthesize_requires_auth() -> None:
    anonymous = TestClient(app)
    response = anonymous.post("/api/v1/voice/synthesize", json={"text": "hello"})
    assert response.status_code == 401


def test_synthesize_returns_501_when_provider_unconfigured() -> None:
    """TTS_PROVIDER is unset in tests -> must degrade gracefully, never a 500."""
    client = _login()
    response = client.post("/api/v1/voice/synthesize", json={"text": "hello"})
    assert response.status_code == 501


def test_synthesize_returns_audio_when_provider_configured(monkeypatch) -> None:
    from app.api.v1.endpoints import voice as voice_endpoint

    monkeypatch.setattr(voice_endpoint, "synthesize", lambda text: b"fake-mp3-bytes")
    client = _login()
    response = client.post("/api/v1/voice/synthesize", json={"text": "hello"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"fake-mp3-bytes"


def test_synthesize_rejects_empty_text() -> None:
    client = _login()
    response = client.post("/api/v1/voice/synthesize", json={"text": ""})
    assert response.status_code == 422
