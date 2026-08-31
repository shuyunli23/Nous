"""Vector store abstraction for skill embeddings.

Two backends behind one interface:

- ``chroma``: persistent ChromaDB collection (default)
- ``memory``: in-process dict, used for tests and as a fallback when Chroma
  cannot be initialised

Only ids and small metadata live in the vector store; PostgreSQL remains the
source of truth for skill content, so the index can always be rebuilt via
``/api/v1/skills/reindex``.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.core.config import settings
from app.core.logging import get_logger
from app.llm.embeddings import cosine_similarity

logger = get_logger(__name__)


class SearchHit:
    """One vector search result."""

    __slots__ = ("skill_id", "similarity", "metadata")

    def __init__(
        self, skill_id: str, similarity: float, metadata: dict[str, Any]
    ) -> None:
        self.skill_id = skill_id
        self.similarity = similarity
        self.metadata = metadata

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<SearchHit {self.skill_id[:8]} sim={self.similarity:.3f}>"


class VectorStore(ABC):
    """Interface every backend must satisfy."""

    @abstractmethod
    def upsert(
        self,
        *,
        skill_id: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None: ...

    @abstractmethod
    def delete(self, skill_id: str) -> None: ...

    @abstractmethod
    def query(
        self,
        *,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def reset(self) -> None: ...


# ── in-memory backend ─────────────────────────────────────────────────────


class MemoryVectorStore(VectorStore):
    """Brute-force cosine search. Fine for the scale of a personal skill library."""

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def upsert(
        self, *, skill_id: str, embedding: list[float], metadata: dict[str, Any]
    ) -> None:
        with self._lock:
            self._vectors[skill_id] = list(embedding)
            self._metadata[skill_id] = dict(metadata)

    def delete(self, skill_id: str) -> None:
        with self._lock:
            self._vectors.pop(skill_id, None)
            self._metadata.pop(skill_id, None)

    def query(
        self,
        *,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        with self._lock:
            items = list(self._vectors.items())
            metadata = dict(self._metadata)

        hits: list[SearchHit] = []
        for skill_id, vector in items:
            meta = metadata.get(skill_id, {})
            if where and not _matches(meta, where):
                continue
            hits.append(
                SearchHit(skill_id, cosine_similarity(embedding, vector), meta)
            )
        hits.sort(key=lambda hit: hit.similarity, reverse=True)
        return hits[:top_k]

    def count(self) -> int:
        with self._lock:
            return len(self._vectors)

    def reset(self) -> None:
        with self._lock:
            self._vectors.clear()
            self._metadata.clear()


# ── chroma backend ────────────────────────────────────────────────────────


class ChromaVectorStore(VectorStore):
    """Persistent ChromaDB collection."""

    def __init__(self) -> None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        path = settings.chroma_path
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        # Cosine space matches how we compare embeddings elsewhere.
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "chroma_ready",
            path=str(path),
            collection=settings.chroma_collection,
            count=self._collection.count(),
        )

    def upsert(
        self, *, skill_id: str, embedding: list[float], metadata: dict[str, Any]
    ) -> None:
        self._collection.upsert(
            ids=[skill_id],
            embeddings=[embedding],
            metadatas=[_clean_metadata(metadata)],
        )

    def delete(self, skill_id: str) -> None:
        self._collection.delete(ids=[skill_id])

    def query(
        self,
        *,
        embedding: list[float],
        top_k: int,
        where: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, self._collection.count()),
            where=_to_chroma_where(where),
            include=["metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        hits: list[SearchHit] = []
        for idx, skill_id in enumerate(ids):
            distance = distances[idx] if idx < len(distances) else 1.0
            # Chroma cosine distance -> similarity
            hits.append(
                SearchHit(skill_id, 1.0 - float(distance), metadatas[idx] or {})
            )
        return hits

    def count(self) -> int:
        return int(self._collection.count())

    def reset(self) -> None:
        self._client.delete_collection(settings.chroma_collection)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )


# ── factory ───────────────────────────────────────────────────────────────

_store: VectorStore | None = None
_store_lock = threading.Lock()


def get_vector_store() -> VectorStore:
    """Return the process-wide vector store, initialising it on first use."""
    global _store
    if _store is not None:
        return _store

    with _store_lock:
        if _store is not None:
            return _store

        if settings.vector_backend == "memory":
            _store = MemoryVectorStore()
            logger.info("vector_store_ready", backend="memory")
            return _store

        try:
            _store = ChromaVectorStore()
        except Exception as exc:
            # Never let an unavailable vector store break the chat path.
            logger.warning(
                "chroma_init_failed_using_memory", error=str(exc)
            )
            _store = MemoryVectorStore()
        return _store


def reset_vector_store() -> None:
    """Drop the cached instance (tests / after config changes)."""
    global _store
    with _store_lock:
        _store = None


# ── helpers ───────────────────────────────────────────────────────────────


def _to_chroma_where(where: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate a flat filter dict into Chroma's expected shape.

    Chroma rejects multi-key filters like ``{"user_id": x, "status": y}`` with
    "Expected where to have exactly one operator" and requires them to be
    wrapped in ``$and``. The flat form is kept as the internal convention
    because it is what the memory backend and callers use.
    """
    if not where:
        return None
    if len(where) == 1:
        return dict(where)
    return {"$and": [{key: value} for key, value in where.items()]}


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Chroma only accepts scalar metadata values."""
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        elif isinstance(value, (list, tuple)):
            cleaned[key] = ",".join(str(item) for item in value)
        else:
            cleaned[key] = str(value)
    return cleaned


def _matches(metadata: dict[str, Any], where: dict[str, Any]) -> bool:
    """Minimal Chroma-compatible ``where`` evaluation for the memory backend."""
    for key, condition in where.items():
        value = metadata.get(key)
        if isinstance(condition, dict):
            for operator, expected in condition.items():
                if operator == "$eq" and value != expected:
                    return False
                if operator == "$ne" and value == expected:
                    return False
                if operator == "$in" and value not in expected:
                    return False
                if operator == "$nin" and value in expected:
                    return False
        elif value != condition:
            return False
    return True
