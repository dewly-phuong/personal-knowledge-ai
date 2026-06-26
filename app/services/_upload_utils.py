"""
Pure utility helpers for upload artifact processing.
No I/O except file reads; no MongoDB; no side effects beyond filesystem reads.
"""

import datetime
import hashlib
import re
from pathlib import Path
from typing import Any

MAX_CONTEXT_CHARS = 12000
MAX_SNIPPET_CHARS = 900
DEFAULT_CHUNK_CHARS = 2000
DEFAULT_CHUNK_OVERLAP_CHARS = 250


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def safe_name(value: str, fallback: str = "uploaded-file") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip(".-")
    return cleaned[:120] or fallback


def slug(value: str, fallback: str = "sheet") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return cleaned[:80] or fallback


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def text_snippets(text: str, query: str, limit: int = 5) -> list[str]:
    words = [
        re.escape(w.lower())
        for w in re.findall(r"[\w\-À-ỹ]+", query or "")
        if len(w) >= 2
    ]
    if not words:
        return [text[:MAX_SNIPPET_CHARS]] if text else []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    scored = []
    for idx, line in enumerate(lines):
        lowered = line.lower()
        score = sum(1 for word in words if re.search(word, lowered))
        if score:
            start = max(0, idx - 2)
            end = min(len(lines), idx + 3)
            snippet = "\n".join(lines[start:end])
            scored.append((score, idx, snippet[:MAX_SNIPPET_CHARS]))
    scored.sort(key=lambda item: (-item[0], item[1]))

    snippets: list[str] = []
    seen: set[str] = set()
    for _, _, snippet in scored:
        key = snippet[:120]
        if key in seen:
            continue
        snippets.append(snippet)
        seen.add(key)
        if len(snippets) >= limit:
            break
    return snippets or ([text[:MAX_SNIPPET_CHARS]] if text else [])


def chunk_text(
    text: str,
    target_chars: int = DEFAULT_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[dict[str, Any]]:
    if target_chars <= 0:
        raise ValueError("target_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= target_chars:
        raise ValueError(
            "overlap_chars must be non-negative and smaller than target_chars"
        )

    content = text or ""
    if not content:
        return []

    chunks: list[dict[str, Any]] = []
    step = target_chars - overlap_chars
    start = 0
    while start < len(content):
        end = min(len(content), start + target_chars)
        chunk = content[start:end]
        chunks.append(
            {
                "index": len(chunks),
                "start_char": start,
                "end_char": end,
                "char_count": len(chunk),
                "text": chunk,
            }
        )
        if end >= len(content):
            break
        start += step
    return chunks


def rank_text_chunks(
    chunks: list[dict[str, Any]],
    query: str,
    limit: int = 6,
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    terms = [
        term.lower()
        for term in re.findall(r"[\w\-À-ỹ]+", query or "")
        if len(term) >= 2
    ]
    if not terms:
        return chunks[:limit]

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for chunk in chunks:
        text = str(chunk.get("text", "")).lower()
        score = sum(text.count(term) for term in terms)
        if score:
            scored.append((score, int(chunk.get("index", 0)), chunk))

    if not scored:
        return chunks[:limit]

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _, _, chunk in scored[:limit]]


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def frame_summary(df, sheet_name: str | None = None) -> dict[str, Any]:
    columns = [
        {
            "name": str(col),
            "dtype": str(dtype),
            "non_null": int(df[col].notna().sum()),
            "null_count": int(df[col].isna().sum()),
        }
        for col, dtype in df.dtypes.items()
    ]
    numeric = df.select_dtypes(include="number")
    numeric_stats = {}
    if not numeric.empty:
        stats = numeric.describe().fillna("").to_dict()
        numeric_stats = {
            str(col): {str(k): jsonable(v) for k, v in values.items()}
            for col, values in stats.items()
        }
    sample_rows = [
        {str(k): jsonable(v) for k, v in row.items()}
        for row in df.head(10).to_dict(orient="records")
    ]
    return {
        "sheet_name": sheet_name,
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": columns,
        "sample_rows": sample_rows,
        "numeric_stats": numeric_stats,
    }


def read_text_or_markitdown(path: Path) -> tuple[str, str]:
    if path.suffix.lower() in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="replace"), "text"
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise ImportError(
            "markitdown is required. Install with: uv add 'markitdown[all]'"
        )
    result = MarkItDown().convert(str(path))
    return result.text_content or "", "markitdown"
