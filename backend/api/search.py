"""
api/search.py — Search endpoints.

  GET  /api/v3/ask?q=...          Simple question → clean JSON answer
  POST /api/v3/search             Full RAG pipeline (existing contract)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.core.response_generator import NvidiaError
from backend.models.schemas import AskResponse, ErrorResponse, SearchRequest, SearchResponse
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ─────────────────────────────────────────
#  GET /api/v3/ask
# ─────────────────────────────────────────

@router.get(
    "/ask",
    response_model=AskResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Missing query"},
        503: {"model": ErrorResponse, "description": "LLM unavailable"},
    },
    summary="Ask a question — returns a clean JSON answer via NVIDIA LLM",
)
async def ask(
    request: Request,
    q: str = Query(..., min_length=1, max_length=2000, description="Your question"),
) -> AskResponse:
    """
    Minimal GET endpoint. Sends `q` directly to NVIDIA LLM.

    Example:
        GET /api/v3/ask?q=How+do+I+reset+my+VPN+password
    """
    pipeline = getattr(request.app.state, "rag_pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG pipeline not initialised. Please retry.",
        )

    logger.info("GET /ask q='{}'", q[:100])

    try:
        answer, latency_ms = pipeline.generator.generate(q)
    except NvidiaError as exc:
        logger.error("NVIDIA error: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {exc}",
        )
    except Exception as exc:
        logger.error("Unexpected error in /ask: {}", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return AskResponse(
        question=q,
        answer=answer,
        model=pipeline.generator._model,
        latency_ms=round(latency_ms, 2),
    )


# ─────────────────────────────────────────
#  POST /api/v3/search  (full RAG)
# ─────────────────────────────────────────

@router.post(
    "/search",
    response_model=SearchResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
        500: {"model": ErrorResponse, "description": "Internal error"},
    },
    summary="AI-powered ticket resolution via RAG pipeline",
)
async def search(request: Request, payload: SearchRequest) -> SearchResponse:
    """
    Full RAG endpoint: retrieves KB context, then calls NVIDIA LLM.

    Request body:
    ```json
    {
      "question": "How do I reset my VPN password?",
      "key": "en",
      "history": []
    }
    ```
    """
    pipeline = getattr(request.app.state, "rag_pipeline", None)
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG pipeline not initialised. Please retry.",
        )

    if not pipeline.retriever.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No knowledge base loaded. "
                "Upload and ingest an Excel file via /api/v3/files first."
            ),
        )

    logger.info(
        "POST /search question='{}' lang='{}' history_turns={}",
        payload.question[:100],
        payload.key,
        len(payload.history),
    )

    try:
        result = pipeline.run(
            question=payload.question,
            history=payload.history or [],
        )
    except NvidiaError as exc:
        logger.error("NVIDIA error: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service error: {exc}",
        )
    except RuntimeError as exc:
        logger.error("Pipeline error: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Unexpected error in /search: {}", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
        )

    return result
