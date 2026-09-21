"""
Tests for the Gemini model fallback.

No API key or network is needed: the Gemini client is replaced by a fake that
says, per model, whether to fail or succeed.
"""
import pytest
from fastapi import HTTPException
from google.genai.errors import APIError
from requests.exceptions import ReadTimeout

import main

GOOD_JSON = '{"angles": ["a"], "email_draft": {"subject": "s", "body": "b"}}'


class FakeAPIError(APIError):
    def __init__(self, code):
        Exception.__init__(self, f"{code} fake error")
        self.code = code


class FakeResponse:
    text = GOOD_JSON


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = outcomes  # model name -> exception or response
        self.calls = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        outcome = self.outcomes[model]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def use_client(monkeypatch):
    monkeypatch.setattr(main, "MODEL", "primary")
    monkeypatch.setattr(main, "FALLBACK_MODEL", "fallback")

    def install(outcomes):
        fake = FakeClient(outcomes)
        fake.timeouts = []

        def make_client(timeout_ms=main.SOLO_TIMEOUT_MS):
            fake.timeouts.append(timeout_ms)
            return fake

        monkeypatch.setattr(main, "_client", make_client)
        return fake

    return install


def test_uses_only_the_main_model_when_it_works(use_client):
    fake = use_client({"primary": FakeResponse(), "fallback": FakeResponse()})

    data = main.call_gemini("a bio")

    assert fake.calls == ["primary"]
    assert data["angles"] == ["a"]


@pytest.mark.parametrize("failure", [FakeAPIError(503), FakeAPIError(429), ReadTimeout("slow")])
def test_falls_back_when_the_main_model_is_overloaded_limited_or_slow(use_client, failure):
    fake = use_client({"primary": failure, "fallback": FakeResponse()})

    data = main.call_gemini("a bio")

    assert fake.calls == ["primary", "fallback"]
    assert data["email_draft"]["subject"] == "s"


def test_gives_a_friendly_error_when_both_models_are_overloaded(use_client):
    fake = use_client({"primary": FakeAPIError(503), "fallback": FakeAPIError(503)})

    with pytest.raises(HTTPException) as excinfo:
        main.call_gemini("a bio")

    assert fake.calls == ["primary", "fallback"]
    assert excinfo.value.status_code == 502
    assert "heavy load" in excinfo.value.detail


def test_gives_a_friendly_error_when_both_models_are_too_slow(use_client):
    use_client({"primary": ReadTimeout("slow"), "fallback": ReadTimeout("slow")})

    with pytest.raises(HTTPException) as excinfo:
        main.call_gemini("a bio")

    assert excinfo.value.status_code == 504
    assert "too long" in excinfo.value.detail


def test_other_errors_do_not_trigger_the_fallback(use_client):
    fake = use_client({"primary": FakeAPIError(400), "fallback": FakeResponse()})

    with pytest.raises(HTTPException) as excinfo:
        main.call_gemini("a bio")

    assert fake.calls == ["primary"]
    assert "went wrong" in excinfo.value.detail


@pytest.mark.parametrize("fallback", ["", "primary"])
def test_no_second_attempt_without_a_different_fallback(use_client, monkeypatch, fallback):
    fake = use_client({"primary": FakeAPIError(503)})
    monkeypatch.setattr(main, "FALLBACK_MODEL", fallback)

    with pytest.raises(HTTPException):
        main.call_gemini("a bio")

    assert fake.calls == ["primary"]


def test_each_attempt_gets_a_shorter_timeout_only_when_there_is_a_fallback(use_client, monkeypatch):
    fake = use_client({"primary": FakeResponse()})
    main.call_gemini("a bio")
    assert fake.timeouts == [main.ATTEMPT_TIMEOUT_MS]

    monkeypatch.setattr(main, "FALLBACK_MODEL", "")
    main.call_gemini("a bio")
    assert fake.timeouts[-1] == main.SOLO_TIMEOUT_MS
