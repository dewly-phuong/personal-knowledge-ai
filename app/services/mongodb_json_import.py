import json
import os

from pymongo import ReplaceOne

from app.services.mongodb_import_shared import (
    get_mtime,
    is_unchanged,
    open_db,
    update_meta,
)


def import_json_files_to_mongodb(dir_path: str = "raw/local"):
    if not os.path.exists(dir_path):
        print(f"Directory {dir_path} not found. Skipping JSON import.")
        return {"status": "skipped", "message": "Directory not found."}

    db, meta_col = open_db()
    imported_count = 0
    skipped_count = 0
    skip_dirs = {"csv", "converted"}

    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for filename in files:
            if not filename.endswith(".json"):
                continue
            result = _import_json_file(db, meta_col, root, filename)
            imported_count += int(result == "imported")
            skipped_count += int(result == "skipped")

    return {"status": "success", "imported": imported_count, "skipped": skipped_count}


def _import_json_file(db, meta_col, root: str, filename: str) -> str:
    file_path = os.path.join(root, filename)
    try:
        last_modified = get_mtime(file_path)
    except Exception as e:
        print(f"Failed to read file status for {filename}: {e}")
        return "failed"

    if is_unchanged(meta_col, filename, last_modified):
        return "skipped"

    print(f"Importing JSON file to MongoDB: {filename} -> collection: {filename[:-5]}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to parse JSON file {filename}: {e}")
        return "failed"

    data = data if isinstance(data, list) else [data]
    operations = [_replace_operation(item) for item in data]
    if operations:
        try:
            db[os.path.splitext(filename)[0]].bulk_write(operations)
        except Exception as e:
            print(f"Failed to bulk write documents for {filename}: {e}")
            return "failed"

    update_meta(meta_col, filename, last_modified)
    return "imported"


def _replace_operation(item):
    if isinstance(item, dict) and "id" in item:
        return ReplaceOne({"id": item["id"]}, item, upsert=True)
    return ReplaceOne(item, item, upsert=True)
