"""
api/health.py — Health and readiness endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from backend.models.schemas import HealthResponse
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Application health check")
async def health_check(request: Request) -> HealthResponse:
    """
    Returns operational status:
    - NVIDIA API key configured
    - Vector store (ChromaDB) loaded and populated
    - Indexed chunk count
    """
    pipeline = getattr(request.app.state, "rag_pipeline", None)

    nvidia_ok = False
    vector_store_loaded = False
    indexed_chunks = 0

    if pipeline:
        nvidia_ok = pipeline.generator.is_reachable()
        vector_store_loaded = pipeline.retriever.is_ready
        indexed_chunks = pipeline.retriever.indexed_chunks

    return HealthResponse(
        status="healthy" if nvidia_ok else "degraded",
        nvidia_reachable=nvidia_ok,
        faiss_loaded=vector_store_loaded,   # field name preserved for API contract
        indexed_chunks=indexed_chunks,
    )


@router.get("/", summary="Root")
async def root():
    return {"message": "AI Support Automation API v3.0.0", "docs": "/docs"}
