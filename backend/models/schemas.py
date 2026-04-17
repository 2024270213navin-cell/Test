"""
models/schemas.py — Pydantic schemas for all API contracts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
#  Shared / Common
# ─────────────────────────────────────────────

class ContextChunk(BaseModel):
    """A single retrieved knowledge-base chunk returned with the answer."""
    category: str
    question: str
    response: str
    reference_information: Optional[str] = None
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class ConversationTurn(BaseModel):
    """One turn in a multi-turn conversation history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


# ─────────────────────────────────────────────
#  Ask  (GET /api/v3/ask)
# ─────────────────────────────────────────────

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    latency_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
#  Search  (POST /api/v3/search)
# ─────────────────────────────────────────────

class SearchRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="User question")
    key: str = Field(default="en", description="Language key, e.g. 'en'")
    history: list[ConversationTurn] = Field(
        default_factory=list,
        max_length=20,
        description="Conversation history (last N turns)",
    )

    @field_validator("question")
    @classmethod
    def strip_question(cls, v: str) -> str:
        return v.strip()


class SearchResponse(BaseModel):
    response: str
    context: list[ContextChunk]
    model: str
    latency_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
#  File Management
# ─────────────────────────────────────────────

class FileInfo(BaseModel):
    filename: str
    size_bytes: int
    row_count: int
    columns: list[str]
    uploaded_at: datetime
    ingested: bool = False


class IngestRequest(BaseModel):
    filename: str


class IngestResponse(BaseModel):
    filename: str
    chunks_indexed: int
    message: str


class DeleteResponse(BaseModel):
    filename: str
    message: str


# ─────────────────────────────────────────────
#  Health
# ─────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    nvidia_reachable: bool
    faiss_loaded: bool
    indexed_chunks: int
    version: str = "3.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
#  Error
# ─────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
