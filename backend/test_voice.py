"""
Tests for the ElevenLabs text-to-speech feature.

No API key or network is needed: the HTTP call to ElevenLabs is replaced with a
fake that records what was sent and returns a canned response.
"""
import httpx
import pytest
from fastapi.testclient import TestClient

import voice
from main import app

client = TestClient(app)

FAKE_MP3 = b"ID3-fake-mp3-bytes"


def fake_response(status=200, content=FAKE_MP3, text=""):
    request = httpx.Request("POST", "https://api.elevenlabs.io/")
    if status == 200:
        return httpx.Response(200, content=content, request=request)
    return httpx.Response(status, text=text or "error", request=request)


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.delenv("ELEVENLABS_MODEL_ID", raising=False)


def test_synthesize_sends_the_expected_request(api_key, monkeypatch):
    sent = {}

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent.update(kwargs)
        return fake_response()

    monkeypatch.setattr(voice.httpx, "post", fake_post)

    audio = voice.synthesize("Hello there")

    assert audio == FAKE_MP3
    assert sent["url"] == f"{voice.ELEVENLABS_URL}/{voice.DEFAULT_VOICE_ID}"
    assert sent["params"] == {"output_format": "mp3_44100_128"}
    assert sent["headers"]["xi-api-key"] == "test-key"
    assert sent["json"] == {"text": "Hello there", "model_id": voice.DEFAULT_MODEL_ID}


def test_voice_and_model_can_be_overridden(api_key, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "my-voice")
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "my-model")
    sent = {}

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent.update(kwargs)
        return fake_response()

    monkeypatch.setattr(voice.httpx, "post", fake_post)
    voice.synthesize("Hi")

    assert sent["url"].endswith("/my-voice")
    assert sent["json"]["model_id"] == "my-model"


@pytest.mark.parametrize("value", [None, ""])
def test_synthesize_requires_an_api_key(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ELEVENLABS_API_KEY", value)
    with pytest.raises(voice.VoiceNotConfigured):
        voice.synthesize("Hi")


@pytest.mark.parametrize(
    "status, expected",
    [
        (401, "API key"),
        (429, "busy"),
        (402, "plan"),
        (500, "went wrong"),
    ],
)
def test_error_statuses_become_friendly_messages(api_key, monkeypatch, status, expected):
    monkeypatch.setattr(voice.httpx, "post", lambda url, **kw: fake_response(status))
    with pytest.raises(voice.VoiceServiceError) as excinfo:
        voice.synthesize("Hi")
    assert expected in excinfo.value.user_message


def test_network_failure_becomes_a_service_error(api_key, monkeypatch):
    def broken_post(url, **kwargs):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(voice.httpx, "post", broken_post)
    with pytest.raises(voice.VoiceServiceError):
        voice.synthesize("Hi")


def test_speak_endpoint_returns_mp3_audio(monkeypatch):
    monkeypatch.setattr("main.synthesize", lambda text: FAKE_MP3)

    response = client.post("/speak", json={"text": "Read this aloud"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == FAKE_MP3


def test_speak_endpoint_says_so_when_voice_is_not_set_up(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    response = client.post("/speak", json={"text": "Read this aloud"})

    assert response.status_code == 503
    assert "ELEVENLABS_API_KEY" in response.json()["detail"]


def test_speak_endpoint_returns_502_when_the_voice_service_fails(api_key, monkeypatch):
    monkeypatch.setattr(voice.httpx, "post", lambda url, **kw: fake_response(429))

    response = client.post("/speak", json={"text": "Read this aloud"})

    assert response.status_code == 502
    assert "busy" in response.json()["detail"]
    assert "test-key" not in response.text  # the key never leaks to the browser


@pytest.mark.parametrize("text", ["", "x" * 2501])
def test_speak_endpoint_validates_text_length(text):
    response = client.post("/speak", json={"text": text})
    assert response.status_code == 422
