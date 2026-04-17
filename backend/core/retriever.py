"""
core/retriever.py — ChromaDB-backed semantic retrieval using sentence-transformers.

Replaces FAISS with ChromaDB for Python 3.11+ compatibility and pip-only install.

Responsibilities:
  • Build / reload a ChromaDB collection from knowledge-base records
  • Persist collection to disk via ChromaDB's PersistentClient
  • Retrieve top-k most relevant chunks for a query (cosine similarity)

Drop-in replacement for the FAISS Retriever — public API is identical.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from backend.config import get_settings
from backend.models.schemas import ContextChunk
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Fixed collection name — one KB per deployment
_COLLECTION_NAME = "knowledge_base"


class Retriever:
    """
    Semantic retriever backed by ChromaDB and sentence-transformers.

    Embeddings are generated externally (sentence-transformers) and stored
    inside ChromaDB's persistent collection so no separate index file is needed.

    Usage:
        retriever = Retriever()
        retriever.build_index(records)          # first time / rebuild
        chunks = retriever.retrieve("my query")
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model: Optional[SentenceTransformer] = None
        self._top_k = self._settings.retriever_top_k
        self._persist_path = Path(self._settings.chroma_persist_dir)

        # PersistentClient writes to disk automatically on every mutation
        self._client = chromadb.PersistentClient(
            path=str(self._persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Try loading an existing collection at startup
        self._collection: Optional[chromadb.Collection] = self._try_load_collection()

    # ─────────────────────────────────────────
    #  Public API  (identical surface to FAISS Retriever)
    # ─────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True when collection exists and contains at least one vector."""
        if self._collection is None:
            return False
        try:
            return self._collection.count() > 0
        except Exception:
            return False

    @property
    def indexed_chunks(self) -> int:
        """Number of vectors currently stored in the collection."""
        if self._collection is None:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    def build_index(self, records: list[dict]) -> int:
        """
        (Re)build ChromaDB collection from a list of knowledge-base records.
        Each record must have a 'text' key used for embedding.

        Existing collection is deleted and recreated to guarantee a clean slate.
        Returns the number of indexed vectors.
        """
        if not records:
            raise ValueError("Cannot build index from empty records list.")

        logger.info("Building ChromaDB collection for {} records …", len(records))
        model = self._get_model()

        texts = [r["text"] for r in records]
        embeddings: np.ndarray = model.encode(
            texts,
            batch_size=64,
            show_progress_bar=True,
            normalize_embeddings=True,   # L2-normalise → cosine via inner product
            convert_to_numpy=True,
        ).astype(np.float32)

        # Drop + recreate collection for a clean rebuild
        try:
            self._client.delete_collection(_COLLECTION_NAME)
            logger.debug("Deleted existing ChromaDB collection '{}'.", _COLLECTION_NAME)
        except Exception:
            pass  # collection didn't exist yet — fine

        # cosine space: distance = 1 − cosine_similarity  (range 0 … 2)
        self._collection = self._client.create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # Build parallel metadata list (strip 'text' key — stored as document)
        metadatas = [
            {
                "category": r.get("category", ""),
                "question": r.get("question", ""),
                "response": r.get("response", ""),
                "reference_information": r.get("reference_information", ""),
            }
            for r in records
        ]

        # ChromaDB requires string IDs
        ids = [str(i) for i in range(len(records))]

        self._collection.add(
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )

        total = self._collection.count()
        logger.info(
            "ChromaDB collection built: {} vectors, dim={}",
            total,
            embeddings.shape[1],
        )
        return total

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[ContextChunk]:
        """
        Return top-k ContextChunk objects for the given query.

        Raises:
            RuntimeError: If no collection is loaded.
        """
        if not self.is_ready:
            raise RuntimeError(
                "ChromaDB collection is not loaded. "
                "Upload and ingest a knowledge base first."
            )

        k = top_k or self._top_k
        model = self._get_model()

        q_embedding: np.ndarray = model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)

        results = self._collection.query(
            query_embeddings=q_embedding.tolist(),
            n_results=min(k, self._collection.count()),  # guard: k ≤ total docs
            include=["metadatas", "distances"],
        )

        chunks: list[ContextChunk] = []
        for meta, distance in zip(
            results["metadatas"][0],
            results["distances"][0],
        ):
            # cosine space: distance = 1 − cosine_sim  →  similarity = 1 − distance
            # clip to [0, 1] to mirror the old np.clip(score, 0.0, 1.0) behaviour
            similarity_score = float(np.clip(1.0 - distance, 0.0, 1.0))
            chunks.append(
                ContextChunk(
                    category=meta.get("category", ""),
                    question=meta.get("question", ""),
                    response=meta.get("response", ""),
                    reference_information=meta.get("reference_information", ""),
                    similarity_score=similarity_score,
                )
            )

        logger.debug(
            "Retrieved {} chunks for query='{}' (top_k={})",
            len(chunks),
            query[:80],
            k,
        )
        return chunks

    def clear_index(self) -> None:
        """Drop the collection from memory and disk (mirrors FAISS clear_index)."""
        try:
            self._client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass
        self._collection = None
        logger.info("ChromaDB collection cleared.")

    # ─────────────────────────────────────────
    #  Private helpers
    # ─────────────────────────────────────────

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(
                "Loading embedding model '{}' on device='{}'…",
                self._settings.embedding_model,
                self._settings.embedding_device,
            )
            self._model = SentenceTransformer(
                self._settings.embedding_model,
                device=self._settings.embedding_device,
            )
            logger.info("Embedding model loaded.")
        return self._model

    def _try_load_collection(self) -> Optional[chromadb.Collection]:
        """
        Attempt to reattach to an existing persisted ChromaDB collection.
        Returns None (not raises) if collection doesn't exist yet.
        """
        try:
            col = self._client.get_collection(_COLLECTION_NAME)
            count = col.count()
            logger.info(
                "Loaded persisted ChromaDB collection '{}': {} vectors",
                _COLLECTION_NAME,
                count,
            )
            return col
        except Exception as exc:
            logger.info(
                "No persisted ChromaDB collection found — will build on first ingest. ({})",
                exc,
            )
            return None
