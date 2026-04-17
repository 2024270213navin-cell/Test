"""
api/files.py — File management endpoints for knowledge-base Excel files.

Endpoints:
  POST   /api/v3/files/upload        — Upload Excel file
  GET    /api/v3/files               — List uploaded files
  POST   /api/v3/files/{filename}/ingest — Ingest file into FAISS
  DELETE /api/v3/files/{filename}    — Delete uploaded file
  GET    /api/v3/files/{filename}/preview — Preview file contents (first 50 rows)
"""
from __future__ import annotations

import io
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from backend.core.data_processor import DataProcessor
from backend.models.schemas import (
    DeleteResponse,
    FileInfo,
    IngestRequest,
    IngestResponse,
)
from backend.utils.file_manager import FileManager
from backend.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

_file_manager = FileManager()
_data_processor = DataProcessor()

# Tracks which files have been ingested in the current session
_ingested_files: set[str] = set()


@router.post(
    "/files/upload",
    response_model=FileInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a knowledge-base Excel file",
)
async def upload_file(
    file: Annotated[UploadFile, File(description="Excel file (.xlsx or .xls)")],
) -> FileInfo:
    """Upload an Excel knowledge-base file to the server."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        file_info = _file_manager.save_upload(file.filename, content)
        logger.info("Upload complete: '{}'", file.filename)
        return file_info
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Upload failed: {}", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@router.get(
    "/files",
    response_model=list[FileInfo],
    summary="List all uploaded knowledge-base files",
)
async def list_files() -> list[FileInfo]:
    """Return metadata for all uploaded Excel files."""
    files = _file_manager.list_files()
    for f in files:
        f.ingested = f.filename in _ingested_files
    return files


@router.post(
    "/files/{filename}/ingest",
    response_model=IngestResponse,
    summary="Ingest an uploaded file into the ChromaDB vector store",
)
async def ingest_file(filename: str, request: Request) -> IngestResponse:
    """
    Process the Excel file, generate embeddings, and load into FAISS.
    This makes the file's knowledge available to the search endpoint.
    """
    pipeline = getattr(request.app.state, "rag_pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialised.")

    try:
        file_path = _file_manager.get_file_path(filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        df = _data_processor.load_and_validate(file_path)
        records = _data_processor.to_records(df)
        indexed = pipeline.retriever.build_index(records)
        _ingested_files.add(filename)

        logger.info("Ingested '{}': {} chunks indexed", filename, indexed)
        return IngestResponse(
            filename=filename,
            chunks_indexed=indexed,
            message=f"Successfully indexed {indexed} knowledge chunks from '{filename}'.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Ingest failed for '{}': {}", filename, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")


@router.delete(
    "/files/{filename}",
    response_model=DeleteResponse,
    summary="Delete an uploaded file",
)
async def delete_file(filename: str) -> DeleteResponse:
    """Delete the specified uploaded file from disk."""
    try:
        _file_manager.delete_file(filename)
        _ingested_files.discard(filename)
        return DeleteResponse(
            filename=filename,
            message=f"File '{filename}' deleted successfully.",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("Delete failed for '{}': {}", filename, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}")


@router.get(
    "/files/{filename}/preview",
    summary="Preview the first 50 rows of an uploaded file",
)
async def preview_file(filename: str) -> dict:
    """Return the first 50 rows of the file as JSON for UI preview."""
    try:
        file_path = _file_manager.get_file_path(filename)
        df = pd.read_excel(file_path, engine="openpyxl", nrows=50)
        df = df.fillna("")
        return {
            "filename": filename,
            "total_rows_preview": len(df),
            "columns": list(df.columns),
            "rows": df.to_dict(orient="records"),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Preview failed: {exc}")
