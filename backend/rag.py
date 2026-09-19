"""
Outlet matching with RAG (retrieval-augmented generation).

A small knowledge base of media outlets (outlets.json) is embedded with the
Gemini embeddings API and stored in Qdrant, a vector database. For each bio we
embed the text, retrieve the closest outlets by cosine similarity, and hand
them to the model so the pitch is written for the best-fit outlet.

The outlets in outlets.json are fictional sample data for this demo.

Matching is optional: if QDRANT_URL is not set, or Qdrant / the embeddings
API fails, find_outlets() returns an empty list and the app falls back to the
plain pitch generation.
"""
import hashlib
import json
import logging
import os
import threading
from pathlib import Path

from google import genai
from google.genai import types
from qdrant_client import QdrantClient, models

logger = logging.getLogger("rag")

OUTLETS_PATH = Path(__file__).parent / "outlets.json"
COLLECTION = "outlets"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = 768

_lock = threading.Lock()
_qdrant: QdrantClient | None = None
_indexed = False


def load_outlets() -> list[dict]:
    with open(OUTLETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def outlet_document(outlet: dict) -> str:
    """The text we embed for one outlet."""
    return (
        f"{outlet['name']} ({outlet['type']}, {outlet['region']}). "
        f"Covers: {outlet['beat']} "
        f"Audience: {outlet['audience']} "
        f"Responds to pitches about: {outlet['likes']}"
    )


def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """Embed texts with Gemini. task_type is RETRIEVAL_DOCUMENT for the outlets
    we index and RETRIEVAL_QUERY for the bio we search with.

    Pulled out as its own function so tests can replace it.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = genai.Client(api_key=api_key, http_options={"timeout": 15_000})
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )
    return [list(e.values) for e in response.embeddings]


def get_qdrant() -> QdrantClient | None:
    """Return a Qdrant client, or None when QDRANT_URL isn't configured."""
    global _qdrant
    url = os.environ.get("QDRANT_URL")
    if not url:
        return None
    if _qdrant is None:
        _qdrant = QdrantClient(url=url, timeout=10, check_compatibility=False)
    return _qdrant


def _signature(outlets: list[dict]) -> str:
    """Changes whenever the outlets, embedding model or size change, so an
    edited outlets.json is re-indexed automatically."""
    payload = json.dumps(outlets, sort_keys=True) + EMBEDDING_MODEL + str(EMBEDDING_DIMENSIONS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _index_is_current(qdrant: QdrantClient, signature: str, expected: int) -> bool:
    if not qdrant.collection_exists(COLLECTION):
        return False
    if qdrant.count(COLLECTION).count != expected:
        return False
    points, _ = qdrant.scroll(COLLECTION, limit=1, with_payload=True)
    return bool(points) and points[0].payload.get("signature") == signature


def ensure_index(qdrant: QdrantClient) -> None:
    """Make sure the outlets are embedded and stored in Qdrant (done once)."""
    global _indexed
    if _indexed:
        return
    with _lock:
        if _indexed:
            return
        outlets = load_outlets()
        signature = _signature(outlets)
        if not _index_is_current(qdrant, signature, len(outlets)):
            vectors = embed_texts(
                [outlet_document(o) for o in outlets], "RETRIEVAL_DOCUMENT"
            )
            if qdrant.collection_exists(COLLECTION):
                qdrant.delete_collection(COLLECTION)
            qdrant.create_collection(
                COLLECTION,
                vectors_config=models.VectorParams(
                    size=EMBEDDING_DIMENSIONS, distance=models.Distance.COSINE
                ),
            )
            qdrant.upsert(
                COLLECTION,
                points=[
                    models.PointStruct(
                        id=i, vector=vector, payload={**outlet, "signature": signature}
                    )
                    for i, (outlet, vector) in enumerate(zip(outlets, vectors))
                ],
            )
        _indexed = True


def find_outlets(bio: str, limit: int = 3) -> list[dict]:
    """Return the outlets whose profile is closest to the bio, best first.

    Returns [] if matching is disabled or anything goes wrong, so the caller
    can carry on without it.
    """
    global _indexed
    qdrant = get_qdrant()
    if qdrant is None:
        return []
    try:
        ensure_index(qdrant)
        [vector] = embed_texts([bio], "RETRIEVAL_QUERY")
        hits = qdrant.query_points(
            COLLECTION, query=vector, limit=limit, with_payload=True
        ).points
    except Exception as exc:  # matching is optional, never break the request
        logger.warning("Outlet matching skipped: %s", exc)
        _indexed = False  # re-check the index on the next request
        return []
    return [
        {
            "name": hit.payload["name"],
            "type": hit.payload["type"],
            "region": hit.payload["region"],
            "beat": hit.payload["beat"],
            "score": round(hit.score, 3),
        }
        for hit in hits
    ]


def reset() -> None:
    """Forget cached state. Used by tests."""
    global _qdrant, _indexed
    _qdrant = None
    _indexed = False
