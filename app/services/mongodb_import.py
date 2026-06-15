import os
import json
import datetime
from pymongo import MongoClient, ReplaceOne

def import_json_files_to_mongodb(dir_path: str = "raw/local"):
    """
    Scans dir_path for JSON files and imports/upserts them into MongoDB
    under the 'personal_knowledge_ai' database.
    Checks file modification dates to prevent duplicate imports.
    """
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(mongo_uri)
    db = client["personal_knowledge_ai"]
    metadata_col = db["_ingest_metadata"]

    if not os.path.exists(dir_path):
        print(f"Directory {dir_path} not found. Skipping JSON import.")
        return {"status": "skipped", "message": "Directory not found."}

    imported_count = 0
    skipped_count = 0

    for filename in os.listdir(dir_path):
        if not filename.endswith(".json"):
            continue
        
        file_path = os.path.join(dir_path, filename)
        collection_name = os.path.splitext(filename)[0]
        
        # Get last modified time
        try:
            mtime = os.path.getmtime(file_path)
            last_modified = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).isoformat()
        except Exception as e:
            print(f"Failed to read file status for {filename}: {e}")
            continue
        
        # Check against metadata collection
        meta = metadata_col.find_one({"filepath": filename})
        if meta and meta.get("last_modified") == last_modified:
            skipped_count += 1
            continue

        # Load file content
        print(f"Importing JSON file to MongoDB: {filename} -> collection: {collection_name}")
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"Failed to parse JSON file {filename}: {e}")
                continue

        if not isinstance(data, list):
            data = [data]

        # Upsert elements using 'id' field
        operations = []
        for item in data:
            if isinstance(item, dict) and "id" in item:
                operations.append(
                    ReplaceOne({"id": item["id"]}, item, upsert=True)
                )
            else:
                # If no id, fallback to replacing the document if it matches completely, or insert
                # Using item as the filter
                operations.append(
                    ReplaceOne(item, item, upsert=True)
                )

        if operations:
            try:
                db[collection_name].bulk_write(operations)
            except Exception as e:
                print(f"Failed to bulk write documents for {filename}: {e}")
                continue

        # Update metadata
        metadata_col.update_one(
            {"filepath": filename},
            {"$set": {"last_modified": last_modified, "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}},
            upsert=True
        )
        imported_count += 1

    return {"status": "success", "imported": imported_count, "skipped": skipped_count}
