"""
tests/test_core.py — Unit tests for DataProcessor, PromptGenerator, and RAG schemas.
Run with: pytest tests/ -v
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.core.data_processor import DataProcessor
from backend.core.prompt_generator import PromptGenerator
from backend.models.schemas import (
    ContextChunk,
    ConversationTurn,
    SearchRequest,
    SearchResponse,
)


# ─────────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Category": ["VPN", "Email", "Hardware"],
            "Question": [
                "How do I reset my VPN password?",
                "Why is Outlook not syncing?",
                "My laptop keyboard is broken.",
            ],
            "Response": [
                "Navigate to the VPN portal and click 'Forgot Password'.",
                "Check your Exchange account settings and re-enter credentials.",
                "Submit a hardware replacement request via the service portal.",
            ],
            "Reference Information": ["KB0001", "KB0002", "KB0003"],
        }
    )


@pytest.fixture
def sample_excel(tmp_path: Path, sample_df: pd.DataFrame) -> Path:
    path = tmp_path / "kb.xlsx"
    sample_df.to_excel(path, index=False)
    return path


@pytest.fixture
def processor() -> DataProcessor:
    return DataProcessor()


@pytest.fixture
def prompt_gen() -> PromptGenerator:
    return PromptGenerator()


@pytest.fixture
def context_chunks() -> list[ContextChunk]:
    return [
        ContextChunk(
            category="VPN",
            question="How do I reset my VPN password?",
            response="Navigate to the VPN portal and click 'Forgot Password'.",
            reference_information="KB0001",
            similarity_score=0.91,
        )
    ]


# ─────────────────────────────────────────────
#  DataProcessor tests
# ─────────────────────────────────────────────

class TestDataProcessor:
    def test_load_valid_file(self, processor: DataProcessor, sample_excel: Path):
        df = processor.load_and_validate(sample_excel)
        assert len(df) == 3
        assert "Question" in df.columns
        assert "Response" in df.columns

    def test_missing_required_columns(self, processor: DataProcessor, tmp_path: Path):
        bad_df = pd.DataFrame({"Title": ["x"], "Body": ["y"]})
        path = tmp_path / "bad.xlsx"
        bad_df.to_excel(path, index=False)
        with pytest.raises(ValueError, match="missing required columns"):
            processor.load_and_validate(path)

    def test_file_not_found(self, processor: DataProcessor):
        with pytest.raises(FileNotFoundError):
            processor.load_and_validate("/nonexistent/file.xlsx")

    def test_to_records(self, processor: DataProcessor, sample_excel: Path):
        df = processor.load_and_validate(sample_excel)
        records = processor.to_records(df)
        assert len(records) == 3
        assert all("text" in r for r in records)
        assert all("question" in r for r in records)

    def test_embedding_text_contains_all_fields(
        self, processor: DataProcessor, sample_excel: Path
    ):
        df = processor.load_and_validate(sample_excel)
        records = processor.to_records(df)
        first = records[0]
        assert "Category: VPN" in first["text"]
        assert "Question:" in first["text"]
        assert "Answer:" in first["text"]

    def test_empty_rows_dropped(self, processor: DataProcessor, tmp_path: Path):
        df = pd.DataFrame(
            {
                "Category": ["VPN", None, "Email"],
                "Question": ["Q1", None, "Q3"],
                "Response": ["A1", "A2", None],
                "Reference Information": ["R1", "R2", "R3"],
            }
        )
        path = tmp_path / "sparse.xlsx"
        df.to_excel(path, index=False)
        result = processor.load_and_validate(path)
        # Row 2 has no Question, row 3 has no Response → both dropped
        assert len(result) == 1

    def test_case_insensitive_columns(self, processor: DataProcessor, tmp_path: Path):
        df = pd.DataFrame(
            {
                "CATEGORY": ["VPN"],
                "QUESTION": ["How?"],
                "RESPONSE": ["Do this."],
                "REFERENCE INFORMATION": ["KB001"],
            }
        )
        path = tmp_path / "upper.xlsx"
        df.to_excel(path, index=False)
        result = processor.load_and_validate(path)
        assert len(result) == 1


# ─────────────────────────────────────────────
#  PromptGenerator tests
# ─────────────────────────────────────────────

class TestPromptGenerator:
    def test_prompt_contains_system_instructions(
        self, prompt_gen: PromptGenerator, context_chunks: list[ContextChunk]
    ):
        prompt = prompt_gen.build_prompt("Test question", context_chunks)
        assert "IT Service Desk" in prompt
        assert "KNOWLEDGE BASE CONTEXT" in prompt

    def test_prompt_contains_question(
        self, prompt_gen: PromptGenerator, context_chunks: list[ContextChunk]
    ):
        question = "How do I reset my VPN?"
        prompt = prompt_gen.build_prompt(question, context_chunks)
        assert question in prompt

    def test_prompt_contains_context(
        self, prompt_gen: PromptGenerator, context_chunks: list[ContextChunk]
    ):
        prompt = prompt_gen.build_prompt("query", context_chunks)
        assert "VPN portal" in prompt
        assert "KB0001" in prompt

    def test_prompt_with_history(
        self,
        prompt_gen: PromptGenerator,
        context_chunks: list[ContextChunk],
    ):
        history = [
            ConversationTurn(role="user", content="I have a VPN problem"),
            ConversationTurn(role="assistant", content="Let me help with that."),
        ]
        prompt = prompt_gen.build_prompt("More details?", context_chunks, history)
        assert "CONVERSATION HISTORY" in prompt
        assert "I have a VPN problem" in prompt

    def test_prompt_no_context(self, prompt_gen: PromptGenerator):
        prompt = prompt_gen.build_prompt("Any question", [])
        assert "No relevant context" in prompt

    def test_history_trimmed_to_max(self, prompt_gen: PromptGenerator):
        history = [
            ConversationTurn(role="user", content=f"Turn {i}")
            for i in range(20)
        ]
        prompt = prompt_gen.build_prompt("Q", [], history)
        # Only last MAX_HISTORY_TURNS * 2 = 6 entries should appear
        assert "Turn 19" in prompt
        assert "Turn 0" not in prompt


# ─────────────────────────────────────────────
#  Schema validation tests
# ─────────────────────────────────────────────

class TestSchemas:
    def test_search_request_strips_whitespace(self):
        req = SearchRequest(question="  my question  ", key="en")
        assert req.question == "my question"

    def test_search_request_empty_question_fails(self):
        with pytest.raises(Exception):
            SearchRequest(question="", key="en")

    def test_context_chunk_score_clamped(self):
        chunk = ContextChunk(
            category="Test",
            question="Q",
            response="A",
            similarity_score=0.75,
        )
        assert 0.0 <= chunk.similarity_score <= 1.0

    def test_conversation_turn_valid_roles(self):
        ConversationTurn(role="user", content="hello")
        ConversationTurn(role="assistant", content="hi")

    def test_conversation_turn_invalid_role(self):
        with pytest.raises(Exception):
            ConversationTurn(role="system", content="hack")
