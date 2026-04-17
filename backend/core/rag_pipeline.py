"""
core/rag_pipeline.py — Orchestrates the full RAG pipeline.

Flow:
  query → Retriever (ChromaDB) → PromptGenerator → ResponseGenerator (NVIDIA) → response
"""
from __future__ import annotations

from backend.core.prompt_generator import PromptGenerator
from backend.core.response_generator import ResponseGenerator
from backend.core.retriever import Retriever
from backend.models.schemas import ContextChunk, ConversationTurn, SearchResponse
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RAGPipeline:
    """
    Wires Retriever → PromptGenerator → ResponseGenerator (NVIDIA LLM).
    Singleton — ChromaDB collection and embedding model shared across requests.
    """

    def __init__(self) -> None:
        self._retriever = Retriever()
        self._prompt_gen = PromptGenerator()
        self._generator = ResponseGenerator()
        logger.info("RAGPipeline initialised.")

    # ─────────────────────────────────────────
    #  Accessors
    # ─────────────────────────────────────────

    @property
    def retriever(self) -> Retriever:
        return self._retriever

    @property
    def generator(self) -> ResponseGenerator:
        """NVIDIA LLM response generator."""
        return self._generator

    # ─────────────────────────────────────────
    #  Main entry point
    # ─────────────────────────────────────────

    def run(
        self,
        question: str,
        history: list[ConversationTurn] | None = None,
    ) -> SearchResponse:
        """
        Execute full RAG pipeline for a user question.

        1. Retrieve top-k context chunks from ChromaDB
        2. Build augmented prompt
        3. Generate response via NVIDIA LLM
        4. Return structured SearchResponse

        Raises:
            RuntimeError: If FAISS index not loaded.
            NvidiaError:  If LLM call fails.
        """
        logger.info("RAG pipeline start: question='{}'", question[:100])

        context_chunks: list[ContextChunk] = self._retriever.retrieve(question)
        logger.debug("Retrieved {} context chunks", len(context_chunks))

        prompt = self._prompt_gen.build_prompt(
            question=question,
            context_chunks=context_chunks,
            history=history,
        )

        response_text, latency_ms = self._generator.generate(prompt)

        result = SearchResponse(
            response=response_text,
            context=context_chunks,
            model=self._generator._model,
            latency_ms=round(latency_ms, 2),
        )

        logger.info(
            "RAG pipeline complete: {:.0f}ms, {} context chunks",
            latency_ms,
            len(context_chunks),
        )
        return result
