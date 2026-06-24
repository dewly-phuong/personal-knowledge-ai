import logging
import os

from chainlit.data import BaseDataLayer
from motor.motor_asyncio import AsyncIOMotorClient

from app.memory.mongodb_feedback import MongoFeedbackMixin
from app.memory.mongodb_steps_elements import MongoStepElementMixin
from app.memory.mongodb_threads import MongoThreadMixin
from app.memory.mongodb_users import MongoUserMixin

logger = logging.getLogger(__name__)
DB_NAME = "personal_knowledge_ai"


class MongoDBDataLayer(
    MongoUserMixin,
    MongoThreadMixin,
    MongoStepElementMixin,
    MongoFeedbackMixin,
    BaseDataLayer,
):
    def __init__(self, mongo_uri: str | None = None):
        super().__init__()
        self._mongo_uri = mongo_uri or os.getenv(
            "MONGO_URI", "mongodb://localhost:27017/"
        )
        self._mongo_client = None
        self._db = None

    def _get_db(self):
        if self._mongo_client is None:
            try:
                self._mongo_client = AsyncIOMotorClient(
                    self._mongo_uri, serverSelectionTimeoutMS=5000
                )
                self._db = self._mongo_client[DB_NAME]
            except Exception as e:
                logger.error(f"MongoDBDataLayer: Failed to connect to MongoDB: {e}")
                raise
        return self._db

    def close(self):
        if self._mongo_client:
            self._mongo_client.close()
            self._mongo_client = None
            self._db = None
