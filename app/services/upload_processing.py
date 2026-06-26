import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.services._upload_utils import (
    MAX_CONTEXT_CHARS,
    chunk_text,
    file_hash,
    now,
    safe_name,
)
from app.services.upload_file_processors import process_file
from app.services.upload_store import get_db, uploads_root


def process_upload(
    file_path: str,
    original_filename: str | None,
    session_id: str,
    user_id: str | None = None,
    mime_type: str | None = None,
) -> dict[str, Any]:
    src = Path(file_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Uploaded file does not exist: {src}")

    filename = safe_name(original_filename or src.name)
    ext = src.suffix.lower()
    sha256 = file_hash(src)
    db = get_db()
    existing = _find_duplicate(db, session_id, sha256, filename)
    if existing:
        return existing

    upload_id = str(uuid.uuid4())
    artifact_dir = (
        uploads_root() / "sessions" / safe_name(session_id, "session") / upload_id
    )
    original_path = _copy_original(src, artifact_dir, filename)
    artifact = _base_artifact(
        upload_id,
        session_id,
        user_id,
        filename,
        mime_type,
        ext,
        src.stat().st_size,
        sha256,
        original_path,
        artifact_dir,
    )
    db["uploaded_artifacts"].replace_one(
        {"upload_id": upload_id}, artifact, upsert=True
    )

    try:
        content, extra, kind, description = process_file(
            original_path, filename, artifact_dir
        )
        artifact.update(
            {
                "kind": kind,
                "status": "processed",
                "processed_at": now(),
                "processed_path": extra.pop("processed_path"),
                "description": description,
                "preview": content[:MAX_CONTEXT_CHARS],
                **_chunk_metadata(content, artifact_dir),
                **extra,
            }
        )
    except Exception as exc:
        artifact.update({"status": "failed", "processed_at": now(), "error": str(exc)})

    db["uploaded_artifacts"].replace_one(
        {"upload_id": upload_id}, artifact, upsert=True
    )
    return artifact


def _find_duplicate(
    db, session_id: str, sha256: str, filename: str
) -> dict[str, Any] | None:
    existing = db["uploaded_artifacts"].find_one(
        {"session_id": session_id, "sha256": sha256, "status": "processed"},
        {"_id": 0},
        sort=[("processed_at", -1), ("created_at", -1)],
    )
    if not existing:
        return None
    db["uploaded_artifacts"].update_one(
        {"upload_id": existing["upload_id"]},
        {
            "$set": {"last_seen_at": now(), "last_duplicate_filename": filename},
            "$inc": {"duplicate_count": 1},
        },
    )
    existing["duplicate"] = True
    existing["last_duplicate_filename"] = filename
    existing["duplicate_count"] = int(existing.get("duplicate_count", 0)) + 1
    return existing


def _copy_original(src: Path, artifact_dir: Path, filename: str) -> Path:
    original_dir = artifact_dir / "original"
    original_dir.mkdir(parents=True, exist_ok=True)
    original_path = original_dir / filename
    if src != original_path:
        shutil.copy2(src, original_path)
    return original_path


def _base_artifact(
    upload_id,
    session_id,
    user_id,
    filename,
    mime_type,
    ext,
    size_bytes,
    sha256,
    original_path,
    artifact_dir,
):
    return {
        "upload_id": upload_id,
        "session_id": session_id,
        "user_id": user_id,
        "original_filename": filename,
        "mime_type": mime_type,
        "file_ext": ext,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "status": "processing",
        "created_at": now(),
        "original_path": str(original_path),
        "artifact_dir": str(artifact_dir),
        "source": "chainlit_upload",
        "duplicate_count": 0,
    }


def _chunk_metadata(content: str, artifact_dir: Path) -> dict[str, Any]:
    chunks = chunk_text(content)
    chunks_path = artifact_dir / "chunks.json"
    chunks_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "chunks_path": str(chunks_path),
        "chunk_count": len(chunks),
        "context_char_count": len(content or ""),
        "retrieval_mode": "chunk_search" if len(chunks) > 1 else "full_preview",
    }
