import csv
import os

from pymongo import ReplaceOne

from app.services.mongodb_import_shared import (
    get_mtime,
    is_unchanged,
    open_db,
    row_hash,
    update_meta,
)


def import_csv_files_to_mongodb(dir_path: str = "raw/local"):
    csv_dir = os.path.join(dir_path, "csv")
    if not os.path.exists(csv_dir):
        print(f"CSV directory {csv_dir} not found. Skipping CSV import.")
        return {"status": "skipped", "message": "CSV directory not found."}

    db, meta_col = open_db()
    imported_count = 0
    skipped_count = 0
    for filename in os.listdir(csv_dir):
        if not filename.endswith(".csv"):
            continue
        result = _import_csv_file(db, meta_col, csv_dir, filename)
        imported_count += int(result == "imported")
        skipped_count += int(result == "skipped")
    return {"status": "success", "imported": imported_count, "skipped": skipped_count}


def _import_csv_file(db, meta_col, csv_dir: str, filename: str) -> str:
    file_path = os.path.join(csv_dir, filename)
    meta_key = f"csv/{filename}"
    try:
        last_modified = get_mtime(file_path)
    except Exception as e:
        print(f"Failed to read file status for {filename}: {e}")
        return "failed"

    if is_unchanged(meta_col, meta_key, last_modified):
        print(f"Skipping CSV file (unchanged): {filename}")
        return "skipped"

    print(f"Importing CSV file to MongoDB: {filename} -> collection: {filename[:-4]}")
    try:
        rows = _read_csv_rows(file_path)
    except Exception as e:
        print(f"Failed to parse CSV file {filename}: {e}")
        return "failed"
    if not rows:
        print(f"  No rows found in {filename}. Skipping.")
        return "failed"

    operations = []
    for row in rows:
        row["_row_key"] = row_hash(row)
        operations.append(ReplaceOne({"_row_key": row["_row_key"]}, row, upsert=True))
    try:
        db[os.path.splitext(filename)[0]].bulk_write(operations)
    except Exception as e:
        print(f"Failed to bulk write documents for {filename}: {e}")
        return "failed"

    update_meta(meta_col, meta_key, last_modified, row_count=len(rows))
    return "imported"


def _read_csv_rows(file_path: str) -> list[dict]:
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return [
            {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
            }
            for row in csv.DictReader(f)
        ]
