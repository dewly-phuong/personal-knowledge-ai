"""
Converts .docx, .pptx, and .pdf files to Markdown using MarkItDown.

Scans a source directory for office/PDF files, converts each one to .md,
and writes the output to a dedicated converted/ subfolder. Already-converted
files whose source has not changed (checked via SHA-256 content hash stored
in MongoDB _ingest_metadata) are skipped automatically.

Usage:
    from app.services.markitdown_converter import convert_office_files
    result = convert_office_files("raw/local")
    # result["converted"] == list of output .md paths that were freshly written
"""

import os
import hashlib
import datetime
from pathlib import Path
from typing import Optional

from pymongo import MongoClient

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".ppt", ".doc"}


def _file_hash(path: str) -> str:
    """SHA-256 of file content — change-detection that's independent of mtime."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_metadata_col(mongo_uri: str):
    client = MongoClient(mongo_uri)
    return client["personal_knowledge_ai"]["_ingest_metadata"]


def convert_office_files(
    src_dir: str = "raw/local",
    out_dir: Optional[str] = None,
    mongo_uri: Optional[str] = None,
) -> dict:
    """
    Convert all .pdf / .docx / .pptx files found directly in src_dir into
    Markdown files written to out_dir (defaults to src_dir/converted/).

    Returns:
        {
          "converted": [list of output .md paths freshly written],
          "skipped":   [list of source paths skipped (unchanged)],
          "failed":    [list of source paths that errored],
        }
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise ImportError(
            "markitdown is required. Install with: uv add 'markitdown[all]'"
        )

    src_path = Path(src_dir).resolve()
    out_path = Path(out_dir).resolve() if out_dir else src_path / "converted"
    out_path.mkdir(parents=True, exist_ok=True)

    mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    meta_col  = _get_metadata_col(mongo_uri)

    md = MarkItDown()

    converted, skipped, failed = [], [], []

    # Only scan top-level of src_dir (not csv/ or converted/ subfolders)
    candidates = [
        f for f in src_path.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    for src_file in sorted(candidates):
        meta_key = f"converted/{src_file.name}"
        src_hash = _file_hash(str(src_file))

        # Skip if hash unchanged since last conversion
        meta = meta_col.find_one({"filepath": meta_key})
        if meta and meta.get("src_hash") == src_hash:
            skipped.append(str(src_file))
            print(f"  [skip]     {src_file.name}  (unchanged)")
            continue

        out_file = out_path / (src_file.stem + ".md")
        print(f"  [convert]  {src_file.name} → {out_file.name}")
        try:
            result = md.convert(str(src_file))
            md_text = result.text_content or ""

            # Prepend a source header so the ingest pipeline knows provenance
            header = (
                f"---\n"
                f"source_file: {src_file.name}\n"
                f"converted_at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
                f"---\n\n"
            )
            out_file.write_text(header + md_text, encoding="utf-8")

            # Persist hash so unchanged files are skipped next run
            meta_col.update_one(
                {"filepath": meta_key},
                {"$set": {
                    "src_hash":     src_hash,
                    "out_path":     str(out_file),
                    "converted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }},
                upsert=True,
            )
            converted.append(str(out_file))

        except Exception as exc:
            print(f"  [error]    {src_file.name}: {exc}")
            failed.append(str(src_file))

    return {"converted": converted, "skipped": skipped, "failed": failed}
