"""
main.py — FastAPI application factory with lifespan, middleware, and router registration.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── ensure project root is on sys.path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.config import get_settings
from backend.core.rag_pipeline import RAGPipeline
from backend.utils.logger import setup_logger, get_logger

# ── API routers (imported after sys.path fix)
from backend.api.search import router as search_router
from backend.api.files import router as files_router
from backend.api.health import router as health_router

settings = get_settings()
setup_logger(settings.log_level)
logger = get_logger(__name__)

# ── Shared application state
_rag_pipeline: RAGPipeline | None = None


def get_rag_pipeline() -> RAGPipeline:
    """FastAPI dependency — returns the shared RAGPipeline singleton."""
    if _rag_pipeline is None:
        raise RuntimeError("RAGPipeline not initialised.")
    return _rag_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle manager."""
    global _rag_pipeline

    logger.info("Starting {} [{}]", settings.app_name, settings.app_env)
    settings.ensure_directories()

    # Initialise RAG pipeline (loads FAISS index if persisted)
    _rag_pipeline = RAGPipeline()
    app.state.rag_pipeline = _rag_pipeline

    logger.info("Application ready — listening on {}:{}", settings.app_host, settings.app_port)
    yield

    logger.info("Shutting down…")


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        description=(
            "AI-powered support automation "
            "with a RAG pipeline backed by NVIDIA LLM and ChromaDB."
        ),
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS
    origins = (
        ["*"]
        if settings.allowed_origins == "*"
        else settings.allowed_origins.split(",")
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers
    app.include_router(health_router, tags=["Health"])
    app.include_router(search_router, prefix="/api/v3", tags=["Search"])
    app.include_router(files_router, prefix="/api/v3", tags=["Files"])

    # ── Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error("Unhandled exception: {}", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )
