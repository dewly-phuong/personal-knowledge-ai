import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
_DB_NAME = "personal_knowledge_ai"
_COL = "system_prompts"


def _col():
    client = AsyncIOMotorClient(_MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[_DB_NAME][_COL]


async def get_active_prompt() -> str | None:
    col = _col()
    doc = await col.find_one({"is_active": True}, sort=[("version", -1)])
    return doc["content"] if doc else None


async def save_prompt(content: str, label: str = "", note: str = "") -> int:
    col = _col()
    last = await col.find_one({}, sort=[("version", -1)])
    version = (last["version"] + 1) if last else 1

    await col.update_many({"is_active": True}, {"$set": {"is_active": False}})
    await col.insert_one(
        {
            "version": version,
            "content": content,
            "label": label,
            "note": note,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return version


async def list_versions() -> list:
    col = _col()
    cursor = col.find({}, {"content": 0}).sort("version", -1)
    return await cursor.to_list(length=100)


async def rollback(version: int) -> bool:
    col = _col()
    doc = await col.find_one({"version": version})
    if not doc:
        return False
    await col.update_many({"is_active": True}, {"$set": {"is_active": False}})
    await col.update_one({"version": version}, {"$set": {"is_active": True}})
    return True
