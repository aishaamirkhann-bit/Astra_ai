"""Read-only voice websocket protocol tests (no wallet/order routes involved)."""
import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app


def _authenticated_client() -> TestClient:
    client = TestClient(app)
    challenge = client.post("/api/v1/auth/login", json={"email": "aisha@astra.ai", "password": "demo1234"})
    assert challenge.status_code == 200, challenge.text
    verified = client.post(
        "/api/v1/auth/verify-otp",
        json={"otp_token": challenge.json()["otp_token"], "code": "123456"},
    )
    assert verified.status_code == 200, verified.text
    client.cookies.set("astra_token", verified.json()["access_token"])
    return client


def test_voice_stream_rejects_anonymous_connections() -> None:
    with pytest.raises(WebSocketDisconnect) as disconnect:
        with TestClient(app).websocket_connect("/ws/voice"):
            pass
    assert disconnect.value.code == 1008


def test_voice_stream_parses_roman_urdu_and_carries_session_context() -> None:
    client = _authenticated_client()
    with client.websocket_connect("/ws/voice") as socket:
        ready = socket.receive_json()
        assert ready["mode"] == "read-only-advisory"

        socket.send_text(json.dumps({"type": "transcript", "text": "gaming laptop 200k se kam", "final": True}))
        result = socket.receive_json()
        assert result["type"] == "transcript"
        assert result["intent"]["category"] == "Laptops & Computers"
        assert result["intent"]["budget_max"] == 200000
        assert result["context"]["budget_max"] == 200000
        assert result["mode"] == "read-only-advisory"
        assert not {"checkout", "order", "wallet_debit", "consent"}.intersection(result)

        socket.send_text(json.dumps({"type": "transcript", "text": "laal shirt size medium", "final": True}))
        followup = socket.receive_json()
        assert followup["intent"]["color"] == "red"
        assert followup["intent"]["size"] == "M"
        assert followup["context"]["budget_max"] == 200000
        assert followup["context"]["color"] == "red"


def test_voice_stream_interrupt_acknowledges_barge_in_and_keeps_new_user_audio(monkeypatch) -> None:
    from app.realtime import voice_ws

    monkeypatch.setattr(voice_ws, "transcribe", lambda audio_bytes, mime: "blue shirt")
    client = _authenticated_client()
    with client.websocket_connect("/ws/voice") as socket:
        socket.receive_json()
        socket.send_text(json.dumps({"type": "audio_start", "mime": "audio/webm"}))
        assert socket.receive_json()["type"] == "listening"
        socket.send_bytes(b"fake-audio-chunk")
        socket.send_text(json.dumps({"type": "interrupt"}))
        interrupted = socket.receive_json()
        assert interrupted["type"] == "interrupted"
        assert interrupted["generation"] == 1

        # Barge-in invalidates assistant output without dropping the user's turn.
        socket.send_text(json.dumps({"type": "audio_end"}))
        transcript = socket.receive_json()
        assert transcript["type"] == "transcript"
        assert transcript["intent"]["color"] == "blue"
        assert socket.receive_json()["type"] == "audio_processed"
