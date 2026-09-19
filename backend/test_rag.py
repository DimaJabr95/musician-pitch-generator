"""
Tests for outlet matching (RAG).

No API key, network or Qdrant server is needed:
- Qdrant runs in its in-memory mode (QdrantClient(":memory:")).
- The Gemini embeddings call is replaced by a small deterministic embedder
  that turns words into a vector, so texts sharing words end up close together.
"""
import re
import zlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

import rag
from main import app, build_contents

client = TestClient(app)

BIO = (
    "Dima is a Damascus-trained violinist based in Dubai. She recently played a "
    "fusion set blending classical violin with Arabic maqam at a Dubai gallery opening."
)

VALID_RESPONSE = {
    "angles": ["A Damascus-trained violinist fuses classical and maqam in Dubai."],
    "email_draft": {"subject": "Maqam meets classical violin", "body": "Hi Maqam Ledger team..."},
}


def fake_embed(texts, task_type):
    """Deterministic stand-in for Gemini embeddings: hashed bag of words."""
    vectors = []
    for text in texts:
        vector = [0.0] * rag.EMBEDDING_DIMENSIONS
        for word in re.findall(r"[a-z]+", text.lower()):
            vector[zlib.crc32(word.encode()) % rag.EMBEDDING_DIMENSIONS] += 1.0
        vectors.append(vector)
    return vectors


@pytest.fixture
def memory_qdrant(monkeypatch):
    """A fresh in-memory Qdrant plus the fake embedder, for one test."""
    rag.reset()
    qdrant = QdrantClient(":memory:")
    monkeypatch.setattr(rag, "get_qdrant", lambda: qdrant)
    monkeypatch.setattr(rag, "embed_texts", fake_embed)
    yield qdrant
    rag.reset()


def test_outlets_file_is_well_formed():
    outlets = rag.load_outlets()
    required = {"id", "name", "type", "region", "beat", "audience", "likes"}
    assert len(outlets) >= 5
    assert all(required <= set(o) for o in outlets)
    assert len({o["id"] for o in outlets}) == len(outlets)


def test_find_outlets_returns_best_matches_first(memory_qdrant):
    results = rag.find_outlets(BIO, limit=3)

    assert len(results) == 3
    names = [r["name"] for r in results]
    assert "The Maqam Ledger" in names
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert set(results[0]) == {"name", "type", "region", "beat", "score"}


def test_a_different_bio_matches_different_outlets(memory_qdrant):
    tech_bio = (
        "A producer who builds AI software and music technology tools "
        "for other producers, and writes about technology in creative work."
    )
    results = rag.find_outlets(tech_bio, limit=1)
    assert results[0]["name"] == "Tech & Tempo"


def test_index_is_built_once_and_not_duplicated(memory_qdrant):
    rag.find_outlets(BIO)
    rag._indexed = False  # simulate a restart of the app against the same Qdrant
    rag.find_outlets(BIO)

    assert memory_qdrant.count(rag.COLLECTION).count == len(rag.load_outlets())


def test_index_is_rebuilt_when_outlets_change(memory_qdrant, monkeypatch):
    rag.find_outlets(BIO)
    changed = rag.load_outlets()[:5]
    monkeypatch.setattr(rag, "load_outlets", lambda: changed)
    rag._indexed = False

    rag.find_outlets(BIO)

    assert memory_qdrant.count(rag.COLLECTION).count == 5


def test_find_outlets_is_empty_when_qdrant_is_not_configured(monkeypatch):
    rag.reset()
    monkeypatch.delenv("QDRANT_URL", raising=False)
    assert rag.find_outlets(BIO) == []


def test_find_outlets_is_empty_when_embedding_fails(memory_qdrant, monkeypatch):
    def broken(texts, task_type):
        raise RuntimeError("embeddings API is down")

    monkeypatch.setattr(rag, "embed_texts", broken)
    assert rag.find_outlets(BIO) == []


def test_build_contents_includes_outlets_only_when_present():
    assert build_contents(BIO, None) == BIO
    assert build_contents(BIO, []) == BIO

    outlets = [
        {"name": "The Maqam Ledger", "type": "Music criticism site", "region": "Middle East", "beat": "Arabic music."},
        {"name": "Gulf Stage Weekly", "type": "Events guide", "region": "Gulf", "beat": "Live shows."},
    ]
    text = build_contents(BIO, outlets)
    assert BIO in text
    assert text.index("The Maqam Ledger") < text.index("Gulf Stage Weekly")


def test_endpoint_returns_matched_outlets_and_passes_them_to_the_model(memory_qdrant):
    with patch("main.call_gemini", return_value=VALID_RESPONSE) as model:
        response = client.post("/generate-pitch", json={"bio": BIO})

    assert response.status_code == 200
    body = response.json()
    assert len(body["outlets"]) == 3
    assert body["outlets"][0]["name"]
    # the same outlets were handed to the model
    _, outlets_passed = model.call_args.args
    assert [o["name"] for o in outlets_passed] == [o["name"] for o in body["outlets"]]


def test_endpoint_still_works_without_outlet_matching(monkeypatch):
    rag.reset()
    monkeypatch.delenv("QDRANT_URL", raising=False)
    with patch("main.call_gemini", return_value=VALID_RESPONSE):
        response = client.post("/generate-pitch", json={"bio": BIO})

    assert response.status_code == 200
    assert response.json()["outlets"] == []
    assert response.json()["angles"]
