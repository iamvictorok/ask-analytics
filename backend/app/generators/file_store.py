"""File store — write, resolve, cleanup with audit logging and size guard."""
from __future__ import annotations

import logging
import mimetypes
import time
import uuid
from pathlib import Path

from backend.config import Settings
from backend.app.models import GeneratedFile

logger = logging.getLogger("dhis2_analyst.file_store")


def write_file(
    settings: Settings,
    data: bytes,
    suffix: str,
    content_type: str | None = None,
    session_id: str = "",
) -> GeneratedFile:
    """Write generated file bytes to temp storage with audit logging."""
    # Size guard
    if len(data) > settings.max_file_size_bytes:
        raise ValueError(
            f"Generated file ({len(data):,} bytes) exceeds maximum "
            f"({settings.max_file_size_bytes:,} bytes)"
        )

    file_id = f"{uuid.uuid4().hex}{suffix}"
    path = settings.temp_path / file_id
    path.write_bytes(data)

    ct = content_type or mimetypes.guess_type(file_id)[0] or "application/octet-stream"

    logger.info(
        "file_written",
        extra={
            "file_id": file_id,
            "size_bytes": len(data),
            "content_type": ct,
            "session_id": session_id,
        },
    )

    return GeneratedFile(
        file_id=file_id,
        filename=file_id,
        content_type=ct,
    )


def resolve_file(settings: Settings, file_id: str, session_id: str = "") -> Path | None:
    """Resolve a file ID to its path. Returns None if not found or expired."""
    # Prevent path traversal
    safe = Path(file_id).name
    root = settings.temp_path.resolve()
    path = (root / safe).resolve()
    if not path.is_relative_to(root):
        logger.warning("file_resolve_rejected", extra={"file_id": file_id, "session_id": session_id})
        return None
    if not path.exists() or not path.is_file():
        return None

    # Check age
    age = time.time() - path.stat().st_mtime
    if age > settings.max_file_age_seconds:
        path.unlink(missing_ok=True)
        logger.info("file_expired", extra={"file_id": safe, "age_seconds": int(age)})
        return None

    logger.info(
        "file_download",
        extra={"file_id": safe, "session_id": session_id},
    )
    return path


def cleanup_old_files(settings: Settings) -> int:
    """Remove expired files from temp storage."""
    cutoff = time.time() - settings.max_file_age_seconds
    removed = 0
    for path in settings.temp_path.iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.info("files_cleaned", extra={"removed": removed})
    return removed
