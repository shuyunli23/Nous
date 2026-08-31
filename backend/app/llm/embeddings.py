"""Embedding providers with graceful degradation.

Three backends, selected by ``EMBEDDING_PROVIDER``:

- ``remote``: OpenAI-compatible ``/embeddings`` endpoint (best quality)
- ``local``:  sentence-transformers in-process (offline, needs extra install)
- ``hash``:   deterministic hashing projection (no deps, dev/tests only)

``remote`` falls back to ``hash`` when the key is missing or the call fails and
``EMBEDDING_FALLBACK_TO_HASH=true``, so retrieval never hard-fails the request
path. The active dimension is reported by ``get_dimension()`` because the
vector store must be created with a fixed width.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Sequence

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Width of the deterministic fallback space. Small enough to stay cheap,
# wide enough that unrelated texts rarely collide.
HASH_DIM = 512

_local_model = None  # lazily initialised sentence-transformers model
_active_provider: str | None = None


# ── public API ────────────────────────────────────────────────────────────


def get_dimension() -> int:
    """Vector width for the provider that will actually be used."""
    provider = settings.embedding_provider
    if provider == "hash":
        return HASH_DIM
    if provider == "local":
        return _local_dimension()
    return settings.embedding_dim


def active_provider() -> str:
    """Provider used by the most recent embed call (for diagnostics)."""
    return _active_provider or settings.embedding_provider


async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed a batch of texts. Never raises for provider outages."""
    if not texts:
        return []

    provider = settings.embedding_provider

    if provider == "hash":
        return _mark(_hash_embed_batch(texts), "hash")

    if provider == "local":
        try:
            return _mark(_local_embed_batch(texts), "local")
        except Exception as exc:
            logger.warning("local_embedding_failed", error=str(exc))
            if not settings.embedding_fallback_to_hash:
                raise
            return _mark(_hash_embed_batch(texts), "hash")

    # remote
    try:
        return _mark(await _remote_embed_batch(texts), "remote")
    except Exception as exc:
        logger.warning("remote_embedding_failed", error=str(exc))
        if not settings.embedding_fallback_to_hash:
            raise
        return _mark(_hash_embed_batch(texts), "hash")


async def embed_text(text: str) -> list[float]:
    """Embed a single text."""
    vectors = await embed_texts([text])
    return vectors[0]


def content_hash(text: str) -> str:
    """Stable hash of the embedded source text.

    Stored on the skill row so reindex can skip rows whose text (and provider)
    did not change.
    """
    payload = f"{settings.embedding_provider}:{settings.embedding_model}:{text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity, 0.0 when either vector is degenerate."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── remote ────────────────────────────────────────────────────────────────


async def _remote_embed_batch(texts: Sequence[str]) -> list[list[float]]:
    key = settings.embedding_api_key or settings.llm_api_key
    if not key:
        raise RuntimeError("No embedding API key configured.")

    url = f"{settings.embedding_base_url.rstrip('/')}/embeddings"
    async with httpx.AsyncClient(
        timeout=settings.llm_timeout_seconds,
        headers={"Authorization": f"Bearer {key}"},
    ) as client:
        resp = await client.post(
            url, json={"model": settings.embedding_model, "input": list(texts)}
        )
        resp.raise_for_status()
        payload = resp.json()

    # Providers may return items out of order; sort by index defensively.
    items = sorted(payload["data"], key=lambda item: item.get("index", 0))
    return [item["embedding"] for item in items]


# ── local ─────────────────────────────────────────────────────────────────


def _load_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer  # heavy import

        logger.info("loading_local_embedding_model", model=settings.embedding_local_model)
        _local_model = SentenceTransformer(settings.embedding_local_model)
    return _local_model


def _local_dimension() -> int:
    try:
        return int(_load_local_model().get_sentence_embedding_dimension())
    except Exception:
        return HASH_DIM if settings.embedding_fallback_to_hash else settings.embedding_dim


def _local_embed_batch(texts: Sequence[str]) -> list[list[float]]:
    model = _load_local_model()
    vectors = model.encode(list(texts), normalize_embeddings=True)
    return [list(map(float, vec)) for vec in vectors]


# ── hash fallback ─────────────────────────────────────────────────────────


def _hash_embed_batch(texts: Sequence[str]) -> list[list[float]]:
    return [_hash_embed(text) for text in texts]


def _hash_embed(text: str) -> list[float]:
    """Deterministic bag-of-tokens projection into ``HASH_DIM`` dimensions.

    This is not semantic: it only captures lexical overlap. It exists so the
    system stays runnable (and testable) without network access or model
    downloads; the hybrid retriever's keyword component carries most of the
    signal in that mode.
    """
    vector = [0.0] * HASH_DIM
    for token in _tokenize(text):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        bucket = struct.unpack_from("<I", digest, 0)[0] % HASH_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    """Whitespace + CJK character tokenisation.

    Chinese text carries no spaces, so single characters and adjacent bigrams
    are emitted to give the fallback some overlap signal.
    """
    lowered = text.lower()
    tokens: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            tokens.append("".join(buffer))
            buffer.clear()

    cjk_run: list[str] = []
    for char in lowered:
        if char.isalnum():
            if "\u4e00" <= char <= "\u9fff":
                flush()
                cjk_run.append(char)
                tokens.append(char)
                if len(cjk_run) >= 2:
                    tokens.append("".join(cjk_run[-2:]))
            else:
                cjk_run.clear()
                buffer.append(char)
        else:
            flush()
            cjk_run.clear()
    flush()
    return tokens


def _mark(vectors: list[list[float]], provider: str) -> list[list[float]]:
    global _active_provider
    _active_provider = provider
    return vectors
