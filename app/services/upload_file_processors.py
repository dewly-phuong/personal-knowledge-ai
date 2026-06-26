from pathlib import Path

from app.services._upload_utils import frame_summary, read_text_or_markitdown, slug
from app.services.upload_markdown import (
    document_markdown,
    image_markdown,
    table_markdown,
)

TABLE_EXTENSIONS = {".csv", ".xlsx", ".xls", ".xlsm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif"}


def process_file(original_path: Path, filename: str, artifact_dir: Path):
    if original_path.suffix.lower() in TABLE_EXTENSIONS:
        return process_table(
            original_path, filename, artifact_dir / "csv", artifact_dir
        )
    if original_path.suffix.lower() in IMAGE_EXTENSIONS:
        return process_image(original_path, filename, artifact_dir)
    return process_document(original_path, filename, artifact_dir)


def process_table(
    original_path: Path, filename: str, csv_dir: Path, artifact_dir: Path
):
    import pandas as pd

    csv_dir.mkdir(parents=True, exist_ok=True)
    summaries, generated_csvs = [], []
    if original_path.suffix.lower() == ".csv":
        df = pd.read_csv(original_path)
        summaries.append(frame_summary(df, "CSV"))
        csv_out = csv_dir / f"{Path(filename).stem}.csv"
        df.to_csv(csv_out, index=False)
        generated_csvs.append(str(csv_out))
    else:
        _read_excel_sheets(
            pd, original_path, filename, csv_dir, summaries, generated_csvs
        )

    processed_path = artifact_dir / "table_summary.md"
    content = table_markdown(filename, summaries, generated_csvs)
    processed_path.write_text(content, encoding="utf-8")
    row_count = sum(summary["row_count"] for summary in summaries)
    description = (
        f"Uploaded table `{filename}` parsed with pandas: "
        f"{len(summaries)} sheet(s), {row_count} total row(s)."
    )
    return (
        content,
        _table_extra(processed_path, row_count, summaries, generated_csvs),
        "table",
        description,
    )


def process_document(original_path: Path, filename: str, artifact_dir: Path):
    text, processor = read_text_or_markitdown(original_path)
    processed_path = artifact_dir / "document.md"
    content = document_markdown(filename, text, processor)
    processed_path.write_text(content, encoding="utf-8")
    return (
        content,
        {"processed_path": str(processed_path), "processor": processor},
        "document",
        f"Uploaded document `{filename}` converted to Markdown using {processor}.",
    )


def process_image(original_path: Path, filename: str, artifact_dir: Path):
    artifact_dir.mkdir(parents=True, exist_ok=True)
    processed_path = artifact_dir / "image.md"
    content = image_markdown(filename, str(original_path))
    processed_path.write_text(content, encoding="utf-8")
    return (
        content,
        {
            "processed_path": str(processed_path),
            "processor": "image-metadata",
            "limitations": [
                "Visual content is not extracted yet; this artifact only contains image metadata."
            ],
        },
        "image",
        f"Uploaded image `{filename}` retained as session context.",
    )


def _read_excel_sheets(pd, original_path, filename, csv_dir, summaries, generated_csvs):
    for sheet_name, df in pd.read_excel(original_path, sheet_name=None).items():
        summaries.append(frame_summary(df, sheet_name))
        csv_out = csv_dir / f"{slug(Path(filename).stem)}__{slug(sheet_name)}.csv"
        df.to_csv(csv_out, index=False)
        generated_csvs.append(str(csv_out))


def _table_extra(processed_path, row_count, summaries, generated_csvs) -> dict:
    return {
        "processed_path": str(processed_path),
        "row_count": row_count,
        "sheet_names": [s["sheet_name"] for s in summaries if s.get("sheet_name")],
        "table_summaries": summaries,
        "generated_csvs": generated_csvs,
    }
