"""
utils/file_manager.py — Manages knowledge-base file uploads on disk.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.config import get_settings
from backend.core.data_processor import DataProcessor
from backend.models.schemas import FileInfo
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class FileManager:
    """
    Handles uploading, listing, and deleting knowledge-base Excel files.
    Files are stored under the configured upload directory.
    """

    ALLOWED_EXTENSIONS = {".xlsx", ".xls"}

    def __init__(self) -> None:
        self._settings = get_settings()
        self._upload_dir = Path(self._settings.upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        self._processor = DataProcessor()

    # ─────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────

    def save_upload(self, filename: str, content: bytes) -> FileInfo:
        """
        Save raw file bytes to the upload directory.

        Args:
            filename: Original filename (will be sanitised).
            content:  Raw file bytes.

        Returns:
            FileInfo metadata.

        Raises:
            ValueError: For disallowed file types.
        """
        safe_name = self._sanitise_filename(filename)
        suffix = Path(safe_name).suffix.lower()

        if suffix not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File type '{suffix}' not allowed. "
                f"Accepted: {self.ALLOWED_EXTENSIONS}"
            )

        dest = self._upload_dir / safe_name
        dest.write_bytes(content)
        logger.info("Saved upload: '{}' ({} bytes)", safe_name, len(content))

        return self._build_file_info(dest)

    def list_files(self) -> list[FileInfo]:
        """Return metadata for all uploaded files, sorted by name."""
        files = []
        for path in sorted(self._upload_dir.iterdir()):
            if path.suffix.lower() in self.ALLOWED_EXTENSIONS and path.is_file():
                try:
                    files.append(self._build_file_info(path))
                except Exception as exc:
                    logger.warning("Could not read metadata for '{}': {}", path.name, exc)
        return files

    def get_file_path(self, filename: str) -> Path:
        """Return the full path to an uploaded file."""
        path = self._upload_dir / self._sanitise_filename(filename)
        if not path.exists():
            raise FileNotFoundError(f"File not found: '{filename}'")
        return path

    def delete_file(self, filename: str) -> None:
        """Delete an uploaded file by name."""
        path = self.get_file_path(filename)
        path.unlink()
        logger.info("Deleted file: '{}'", filename)

    def file_exists(self, filename: str) -> bool:
        path = self._upload_dir / self._sanitise_filename(filename)
        return path.exists()

    # ─────────────────────────────────────────
    #  Private helpers
    # ─────────────────────────────────────────

    def _build_file_info(self, path: Path) -> FileInfo:
        """Build a FileInfo object, reading row/column metadata from the Excel file."""
        try:
            meta = self._processor.get_metadata(path)
            row_count = meta["row_count"]
            columns = meta["columns"]
        except Exception:
            row_count = 0
            columns = []

        stat = path.stat()
        return FileInfo(
            filename=path.name,
            size_bytes=stat.st_size,
            row_count=row_count,
            columns=columns,
            uploaded_at=datetime.fromtimestamp(stat.st_mtime),
            ingested=False,  # Ingestion state tracked in-memory by the RAG pipeline
        )

    @staticmethod
    def _sanitise_filename(filename: str) -> str:
        """Strip path separators and whitespace from a filename."""
        name = Path(filename).name  # Removes any directory components
        name = name.replace(" ", "_")
        return name
