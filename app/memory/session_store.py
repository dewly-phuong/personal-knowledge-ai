import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

REDIS_TTL = 86400  # 24 hours
REDIS_KEY_PREFIX = "session:"
DB_NAME = "personal_knowledge_ai"
COLLECTION_NAME = "chat_history"


class SessionStore:
    def __init__(self, redis_client=None, mongo_uri: str = None):
        self._redis = redis_client or get_redis_client()
        self._mongo_uri = mongo_uri or os.getenv(
            "MONGO_URI", "mongodb://localhost:27017/"
        )
        self._mongo_client = None
        self._db = None
        self._collection = None
        self._background_tasks = set()

    def _get_collection(self):
        if self._mongo_client is None:
            try:
                self._mongo_client = AsyncIOMotorClient(
                    self._mongo_uri, serverSelectionTimeoutMS=2000
                )
                self._db = self._mongo_client[DB_NAME]
                self._collection = self._db[COLLECTION_NAME]
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise e
        return self._collection

    async def load(self, session_id: str) -> List[BaseMessage]:
        key = f"{REDIS_KEY_PREFIX}{session_id}"

        # 1. Try Redis cache
        try:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, self._redis.get, key)
            if raw:
                try:
                    return messages_from_dict(json.loads(raw))
                except Exception as e:
                    logger.warning(
                        f"Failed to parse cached history for session {session_id}: {e}"
                    )
        except Exception as e:
            logger.warning(f"Redis error during load for session {session_id}: {e}")

        # 2. Fallback to MongoDB
        try:
            col = self._get_collection()
            doc = await col.find_one({"session_id": session_id})
            if doc and "messages" in doc:
                messages = messages_from_dict(doc["messages"])
                # Seed Redis in the background
                task = asyncio.create_task(self._seed_redis(key, doc["messages"]))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
                return messages
        except Exception as e:
            logger.error(f"MongoDB error during load for session {session_id}: {e}")

        return []

    async def _seed_redis(self, key: str, serialized_messages: list) -> None:
        try:
            loop = asyncio.get_running_loop()
            val = json.dumps(serialized_messages)
            await loop.run_in_executor(
                None, lambda: self._redis.set(key, val, ex=REDIS_TTL)
            )
        except Exception as e:
            logger.warning(f"Failed to seed Redis cache: {e}")

    async def save(self, session_id: str, messages: List[BaseMessage]) -> None:
        key = f"{REDIS_KEY_PREFIX}{session_id}"
        serialized = messages_to_dict(messages)
        val = json.dumps(serialized)

        # 1. Write to Redis (awaited)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, lambda: self._redis.set(key, val, ex=REDIS_TTL)
            )
        except Exception as e:
            logger.warning(f"Redis error during save for session {session_id}: {e}")

        # 2. Background Write to MongoDB
        task = asyncio.create_task(self._save_to_mongo(session_id, serialized))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _save_to_mongo(self, session_id: str, serialized_messages: list) -> None:
        try:
            col = self._get_collection()
            await col.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "messages": serialized_messages,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"MongoDB error during save for session {session_id}: {e}")

    async def clear(self, session_id: str) -> None:
        key = f"{REDIS_KEY_PREFIX}{session_id}"

        # 1. Delete from Redis
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._redis.delete, key)
        except Exception as e:
            logger.warning(f"Redis error during clear for session {session_id}: {e}")

        # 2. Background delete from MongoDB
        task = asyncio.create_task(self._clear_mongo(session_id))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _clear_mongo(self, session_id: str) -> None:
        try:
            col = self._get_collection()
            await col.delete_one({"session_id": session_id})
        except Exception as e:
            logger.error(f"MongoDB error during clear for session {session_id}: {e}")

    async def flush(self) -> None:
        """Wait for all pending background tasks to complete."""
        if self._background_tasks:
            await asyncio.gather(*list(self._background_tasks), return_exceptions=True)

    def close(self) -> None:
        """Close connection to MongoDB."""
        if self._mongo_client:
            self._mongo_client.close()

    async def ping_mongo(self) -> bool:
        """Ping MongoDB and return True if healthy, False otherwise."""
        try:
            col = self._get_collection()
            await col.database.client.admin.command("ping")
            return True
        except Exception as e:
            logger.warning(f"MongoDB health check failed: {e}")
            return False

    async def ping_redis(self) -> bool:
        """Ping Redis and return True if healthy, False otherwise."""
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._redis.ping)
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False
