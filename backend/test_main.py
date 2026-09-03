"""
Tests for the /generate-pitch endpoint.

All tests mock call_gemini directly, so no live API key or network call is
needed to run the suite. This matches the spec: "FastAPI endpoint tests
using mocked responses so tests don't depend on live API calls."
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

VALID_CLAUDE_RESPONSE = {
    "angles": [
        "Classical-meets-Arabic-maqam fusion is a distinctive local-culture story.",
        "A career pivot from IT into professional violin performance is a strong "
        "personal-narrative hook.",
    ],
    "email_draft": {
        "subject": "Dubai violinist blends classical training with Arabic maqam",
        "body": "Hi [Name], thought this might be a fit for your desk — a "
        "Damascus-trained violinist based in Dubai is performing a fusion set...",
    },
}


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_generate_pitch_returns_angles_and_email():
    with patch("main.call_gemini", return_value=VALID_CLAUDE_RESPONSE):
        response = client.post(
            "/generate-pitch",
            json={"bio": "Dima is a Damascus-trained violinist based in Dubai..."},
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["angles"]) == 2
    assert body["email_draft"]["subject"].startswith("Dubai violinist")


def test_generate_pitch_rejects_too_short_bio():
    # Below the 20-character minimum in PitchRequest — should fail validation
    # before call_claude is ever invoked.
    response = client.post("/generate-pitch", json={"bio": "too short"})
    assert response.status_code == 422


def test_generate_pitch_handles_missing_fields_from_claude():
    # Simulates the AI returning malformed/incomplete JSON — the endpoint
    # should fail loudly (502) rather than silently return a broken response.
    with patch("main.call_gemini", return_value={"angles": ["only angles, no email"]}):
        response = client.post(
            "/generate-pitch",
            json={"bio": "Dima is a Damascus-trained violinist based in Dubai..."},
        )
    assert response.status_code == 502
