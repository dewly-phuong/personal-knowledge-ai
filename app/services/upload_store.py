import os
from pathlib import Path

from pymongo import MongoClient


def get_db(mongo_uri: str | None = None):
    uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    return MongoClient(uri)["personal_knowledge_ai"]


def uploads_root() -> Path:
    return Path(os.getenv("UPLOADS_DIR", "uploads")).resolve()
