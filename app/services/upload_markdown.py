import json
from typing import Any

from app.services._upload_utils import jsonable, now


def markdown_table(rows: list[dict[str, Any]], limit: int = 10) -> str:
    if not rows:
        return "_No rows available._"
    rows = rows[:limit]
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        vals = []
        for header in headers:
            val = jsonable(row.get(header))
            text = "" if val is None else str(val)
            vals.append(text.replace("|", "\\|").replace("\n", " ")[:160])
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def table_markdown(
    original_filename: str, summaries: list[dict[str, Any]], generated_csvs: list[str]
) -> str:
    parts = _table_header(original_filename, generated_csvs)
    for summary in summaries:
        _append_sheet_summary(parts, summary)
    return "\n".join(parts).strip() + "\n"


def document_markdown(original_filename: str, text: str, processor: str) -> str:
    return (
        "---\n"
        f"source_file: {original_filename}\n"
        f"processed_at: {now()}\n"
        f"processor: {processor}\n"
        "kind: document\n"
        "---\n\n"
        f"# Uploaded Document: {original_filename}\n\n"
        f"{text.strip()}\n"
    )


def image_markdown(original_filename: str, original_path: str) -> str:
    return (
        "---\n"
        f"source_file: {original_filename}\n"
        f"processed_at: {now()}\n"
        "processor: image-metadata\n"
        "kind: image\n"
        f"original_path: {original_path}\n"
        "---\n\n"
        f"# Uploaded Image: {original_filename}\n\n"
        "This image was uploaded by a Chainlit user and retained as chat-session context.\n\n"
        f"- Original file path: `{original_path}`\n"
    )


def _table_header(original_filename: str, generated_csvs: list[str]) -> list[str]:
    parts = [
        "---",
        f"source_file: {original_filename}",
        f"processed_at: {now()}",
        "processor: pandas",
        "kind: table",
        "---",
        "",
        f"# Uploaded Table: {original_filename}",
        "",
        "This file was uploaded by a Chainlit user and processed for this chat session context.",
        "",
        "## Generated CSV Files",
    ]
    parts.extend(f"- `{path}`" for path in generated_csvs)
    return parts


def _append_sheet_summary(parts: list[str], summary: dict[str, Any]) -> None:
    title = summary.get("sheet_name") or "CSV"
    parts.extend(
        [
            "",
            f"## Sheet: {title}",
            "",
            f"- Rows: {summary['row_count']}",
            f"- Columns: {summary['column_count']}",
            "",
            "### Columns",
            "",
        ]
    )
    for column in summary["columns"]:
        parts.append(
            f"- `{column['name']}` ({column['dtype']}), "
            f"non-null={column['non_null']}, null={column['null_count']}"
        )
    parts.extend(["", "### Sample Rows", "", markdown_table(summary["sample_rows"])])
    if summary["numeric_stats"]:
        parts.extend(
            [
                "",
                "### Numeric Statistics",
                "",
                "```json",
                json.dumps(summary["numeric_stats"], ensure_ascii=False, indent=2),
                "```",
            ]
        )
