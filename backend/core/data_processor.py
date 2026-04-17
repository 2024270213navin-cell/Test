"""
core/data_processor.py — Loads, validates, and pre-processes knowledge-base Excel files.

Expected columns (case-insensitive, leading/trailing whitespace ignored):
  • Category
  • Question
  • Response
  • Reference Information
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.utils.logger import get_logger

logger = get_logger(__name__)

REQUIRED_COLUMNS = {"category", "question", "response", "reference information"}
COLUMN_MAP = {
    "category": "Category",
    "question": "Question",
    "response": "Response",
    "reference information": "Reference Information",
}


class DataProcessor:
    """
    Handles loading, validation, and cleaning of Excel knowledge-base files.

    Usage:
        processor = DataProcessor()
        df = processor.load_and_validate("path/to/file.xlsx")
        records = processor.to_records(df)
    """

    def __init__(self) -> None:
        self._last_file: Optional[str] = None

    # ─────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────

    def load_and_validate(self, file_path: str | Path) -> pd.DataFrame:
        """
        Load an Excel file, validate required columns, clean data,
        and return a normalised DataFrame.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If required columns are missing or the file is empty.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("Loading knowledge base file: {}", file_path.name)
        df = self._read_excel(file_path)
        df = self._normalise_columns(df)
        self._validate_columns(df, file_path.name)
        df = self._clean_data(df)
        self._validate_not_empty(df, file_path.name)

        self._last_file = str(file_path)
        logger.info("Loaded {} rows from '{}'", len(df), file_path.name)
        return df

    def to_records(self, df: pd.DataFrame) -> list[dict]:
        """Convert DataFrame to a list of clean dicts suitable for embedding."""
        records = []
        for _, row in df.iterrows():
            records.append(
                {
                    "category": row["Category"],
                    "question": row["Question"],
                    "response": row["Response"],
                    "reference_information": row.get("Reference Information", ""),
                    # Composite text used for embedding
                    "text": self._build_embedding_text(row),
                }
            )
        return records

    def get_metadata(self, file_path: str | Path) -> dict:
        """Return lightweight metadata without full load (row count, columns)."""
        file_path = Path(file_path)
        df = self._read_excel(file_path)
        return {
            "filename": file_path.name,
            "size_bytes": file_path.stat().st_size,
            "row_count": len(df),
            "columns": list(df.columns),
        }

    # ─────────────────────────────────────────
    #  Private helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _read_excel(file_path: Path) -> pd.DataFrame:
        try:
            return pd.read_excel(file_path, engine="openpyxl")
        except Exception as exc:
            logger.error("Failed to read Excel file '{}': {}", file_path.name, exc)
            raise ValueError(f"Cannot read Excel file '{file_path.name}': {exc}") from exc

    @staticmethod
    def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace and lower-case column names for matching."""
        df.columns = [str(c).strip() for c in df.columns]
        return df

    @staticmethod
    def _validate_columns(df: pd.DataFrame, filename: str) -> None:
        actual_lower = {c.lower() for c in df.columns}
        missing = REQUIRED_COLUMNS - actual_lower
        if missing:
            raise ValueError(
                f"File '{filename}' is missing required columns: {missing}. "
                f"Found: {set(df.columns)}"
            )

    @staticmethod
    def _clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """
        Rename columns to canonical names, drop empty rows,
        and sanitise text content.
        """
        # Build rename map: actual column name → canonical name
        rename_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in COLUMN_MAP:
                rename_map[col] = COLUMN_MAP[col_lower]

        df = df.rename(columns=rename_map)

        # Keep only known columns (drop extras)
        keep_cols = [c for c in COLUMN_MAP.values() if c in df.columns]
        df = df[keep_cols].copy()

        # Drop rows where Question or Response is empty
        df = df.dropna(subset=["Question", "Response"])
        df = df[df["Question"].str.strip() != ""]
        df = df[df["Response"].str.strip() != ""]

        # Fill NaN in optional columns
        for col in ["Category", "Reference Information"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str).str.strip()

        # Normalise text columns
        for col in ["Question", "Response"]:
            df[col] = df[col].astype(str).apply(DataProcessor._clean_text)

        # Reset index
        df = df.reset_index(drop=True)
        return df

    @staticmethod
    def _validate_not_empty(df: pd.DataFrame, filename: str) -> None:
        if df.empty:
            raise ValueError(
                f"File '{filename}' contains no valid rows after cleaning. "
                "Ensure at least one row has non-empty 'Question' and 'Response' columns."
            )

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove excessive whitespace and normalize line endings."""
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _build_embedding_text(row: pd.Series) -> str:
        """
        Concatenate fields into the text that will be embedded.
        Weighting question more gives better semantic retrieval.
        """
        parts = []
        if row.get("Category"):
            parts.append(f"Category: {row['Category']}")
        parts.append(f"Question: {row['Question']}")
        parts.append(f"Answer: {row['Response']}")
        if row.get("Reference Information"):
            parts.append(f"Reference: {row['Reference Information']}")
        return "\n".join(parts)
