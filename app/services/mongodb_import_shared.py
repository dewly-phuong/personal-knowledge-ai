import datetime
import hashlib
import json
import os

from pymongo import MongoClient


def open_db(mongo_uri: str | None = None):
    uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(uri)
    db = client["personal_knowledge_ai"]
    return db, db["_ingest_metadata"]


def get_mtime(file_path: str) -> str:
    mtime = os.path.getmtime(file_path)
    return datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc).isoformat()


def is_unchanged(meta_col, meta_key: str, last_modified: str) -> bool:
    meta = meta_col.find_one({"filepath": meta_key})
    return bool(meta and meta.get("last_modified") == last_modified)


def update_meta(meta_col, meta_key: str, last_modified: str, **extra) -> None:
    meta_col.update_one(
        {"filepath": meta_key},
        {
            "$set": {
                "last_modified": last_modified,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                **extra,
            }
        },
        upsert=True,
    )


def row_hash(row: dict) -> str:
    return hashlib.sha256(
        json.dumps(row, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
