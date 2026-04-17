"""
tests/test_api.py — Integration tests for FastAPI endpoints using TestClient.
Run with: pytest tests/ -v
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.models.schemas import ContextChunk, SearchResponse


# ─────────────────────────────────────────────
#  App fixture with mocked RAG pipeline
# ─────────────────────────────────────────────

@pytest.fixture
def mock_pipeline():
    pipeline = MagicMock()
    pipeline.retriever.is_ready = True
    pipeline.retriever.indexed_chunks = 42
    pipeline.response_generator.is_reachable.return_value = True

    pipeline.run.return_value = SearchResponse(
        response="Please navigate to the VPN portal to reset your password.",
        context=[
            ContextChunk(
                category="VPN",
                question="How do I reset my VPN password?",
                response="Navigate to VPN portal.",
                similarity_score=0.92,
            )
        ],
        model="gemma4:31b-cloud",
        latency_ms=1234.5,
    )
    return pipeline


@pytest.fixture
def client(mock_pipeline):
    from backend.main import create_app

    app = create_app()
    app.state.rag_pipeline = mock_pipeline

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─────────────────────────────────────────────
#  Health endpoint
# ─────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ollama_reachable"] is True
        assert body["faiss_loaded"] is True
        assert body["indexed_chunks"] == 42

    def test_root(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "ServiceNow AI Automation" in resp.json()["message"]


# ─────────────────────────────────────────────
#  Search endpoint
# ─────────────────────────────────────────────

class TestSearchEndpoint:
    def test_valid_search(self, client: TestClient):
        resp = client.post(
            "/api/v3/search",
            json={"question": "How do I reset my VPN?", "key": "en", "history": []},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "response" in body
        assert "context" in body
        assert body["model"] == "gemma4:31b-cloud"

    def test_search_with_history(self, client: TestClient):
        resp = client.post(
            "/api/v3/search",
            json={
                "question": "Still having issues",
                "key": "en",
                "history": [
                    {"role": "user", "content": "VPN not working"},
                    {"role": "assistant", "content": "Try resetting your password."},
                ],
            },
        )
        assert resp.status_code == 200

    def test_empty_question_rejected(self, client: TestClient):
        resp = client.post(
            "/api/v3/search",
            json={"question": "", "key": "en"},
        )
        assert resp.status_code == 422

    def test_search_no_index(self, client: TestClient, mock_pipeline):
        mock_pipeline.retriever.is_ready = False
        resp = client.post(
            "/api/v3/search",
            json={"question": "test", "key": "en"},
        )
        assert resp.status_code == 503

    def test_ollama_error_returns_503(self, client: TestClient, mock_pipeline):
        from backend.core.response_generator import OllamaError
        mock_pipeline.run.side_effect = OllamaError("Ollama unreachable")
        resp = client.post(
            "/api/v3/search",
            json={"question": "test", "key": "en"},
        )
        assert resp.status_code == 503


# ─────────────────────────────────────────────
#  Files endpoint
# ─────────────────────────────────────────────

def _make_excel_bytes() -> bytes:
    df = pd.DataFrame(
        {
            "Category": ["VPN"],
            "Question": ["How to connect?"],
            "Response": ["Use the client."],
            "Reference Information": ["KB001"],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


class TestFilesEndpoint:
    def test_list_files_empty(self, client: TestClient):
        resp = client.get("/api/v3/files")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_upload_valid_file(self, client: TestClient, tmp_path: Path):
        excel_bytes = _make_excel_bytes()
        resp = client.post(
            "/api/v3/files/upload",
            files={"file": ("test_kb.xlsx", excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["filename"] == "test_kb.xlsx"
        assert body["row_count"] == 1

    def test_upload_invalid_extension(self, client: TestClient):
        resp = client.post(
            "/api/v3/files/upload",
            files={"file": ("malicious.exe", b"binary", "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_delete_nonexistent_file(self, client: TestClient):
        resp = client.delete("/api/v3/files/does_not_exist.xlsx")
        assert resp.status_code == 404
