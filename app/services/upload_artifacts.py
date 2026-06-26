"""
Upload artifact processing and context retrieval.

process_upload   — process one file and persist session-scoped artifacts to MongoDB
get_*            — query helpers
build_session_upload_context — format bounded context for the agent
search_artifact_text         — chunk-ranked text search within an artifact
"""

import json
from pathlib import Path
from typing import Any

from app.services._upload_utils import (
    MAX_CONTEXT_CHARS,
    rank_text_chunks,
    text_snippets,
)
from app.services.upload_processing import process_upload
from app.services.upload_store import get_db

__all__ = [
    "build_session_upload_context",
    "get_artifact",
    "get_artifacts_for_session",
    "list_artifacts",
    "process_upload",
    "search_artifact_text",
]


# ── Query helpers ─────────────────────────────────────────────────────────────


def get_artifacts_for_session(
    session_id: str,
    upload_ids: list[str] | None = None,
    limit: int = 10,
    statuses: list[str] | None = None,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {
        "session_id": session_id,
        "status": {"$in": statuses or ["processed"]},
    }
    if upload_ids:
        query["upload_id"] = {"$in": upload_ids}
    return list(
        get_db()["uploaded_artifacts"]
        .find(query, {"_id": 0})
        .sort("processed_at", -1)
        .limit(limit)
    )


def get_artifact(upload_id: str) -> dict[str, Any] | None:
    return get_db()["uploaded_artifacts"].find_one({"upload_id": upload_id}, {"_id": 0})


def list_artifacts(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    query = {"status": status} if status else {}
    return list(
        get_db()["uploaded_artifacts"]
        .find(query, {"_id": 0})
        .sort("created_at", -1)
        .limit(limit)
    )


# ── Context builders ──────────────────────────────────────────────────────────


def build_session_upload_context(
    session_id: str,
    upload_ids: list[str] | None = None,
    max_chars: int = MAX_CONTEXT_CHARS,
    query: str = "",
) -> str:
    artifacts = get_artifacts_for_session(session_id, upload_ids=upload_ids)
    if not artifacts:
        return ""
    parts = [
        "Uploaded file context for this chat session. Use this as temporary session context only.",
    ]
    budget = max_chars
    for artifact in artifacts:
        header = _artifact_header(artifact)
        preview = (
            search_artifact_text(artifact, query=query)
            if query
            else artifact.get("preview", "")
        )
        chunk = header + preview
        if len(chunk) > budget:
            chunk = chunk[:budget]
        parts.append(chunk)
        budget -= len(chunk)
        if budget <= 0:
            break
    return "\n".join(parts).strip()


def search_artifact_text(artifact: dict[str, Any], query: str = "") -> str:
    chunks = _load_chunks(artifact)
    if chunks:
        ranked = rank_text_chunks(chunks, query=query, limit=6)
        return "\n\n---\n\n".join(
            f"[chunk {chunk.get('index')}]\n{chunk.get('text', '')}" for chunk in ranked
        )

    texts = []
    processed_path = artifact.get("processed_path")
    if processed_path and Path(processed_path).exists():
        texts.append(Path(processed_path).read_text(encoding="utf-8", errors="replace"))

    for csv_path in artifact.get("generated_csvs", [])[:5]:
        path = Path(csv_path)
        if path.exists():
            texts.append(
                f"\n\n# CSV Extract: {path.name}\n"
                + path.read_text(encoding="utf-8", errors="replace")[:MAX_CONTEXT_CHARS]
            )

    combined = "\n\n".join(texts) or artifact.get("preview", "")
    snippets = text_snippets(combined, query=query, limit=6)
    return "\n\n---\n\n".join(snippets)


def _artifact_header(artifact: dict[str, Any]) -> str:
    lines = [
        f"\n\n## Upload {artifact['upload_id']}: {artifact['original_filename']}",
        f"- Kind: {artifact.get('kind')}",
        f"- Description: {artifact.get('description')}",
        f"- Processed path: {artifact.get('processed_path')}",
        f"- Retrieval mode: {artifact.get('retrieval_mode', 'full_preview')}",
        f"- Chunks: {artifact.get('chunk_count', 0)}",
        f"- Context chars: {artifact.get('context_char_count', len(artifact.get('preview', '')))}",
    ]
    limitations = artifact.get("limitations") or []
    if limitations:
        lines.append("- Limitations: " + "; ".join(str(item) for item in limitations))
    return "\n".join(lines) + "\n\n"


def _load_chunks(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    chunks_path = artifact.get("chunks_path")
    if not chunks_path:
        return []
    path = Path(chunks_path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
