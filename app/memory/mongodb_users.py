import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from chainlit.user import PersistedUser, User

logger = logging.getLogger(__name__)


class MongoUserMixin:
    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        try:
            db = self._get_db()
            doc = await db["cl_users"].find_one({"identifier": identifier})
            if doc:
                return PersistedUser(
                    id=doc["id"],
                    identifier=doc["identifier"],
                    createdAt=doc.get("createdAt"),
                    metadata=doc.get("metadata", {}),
                    display_name=doc.get("display_name"),
                )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in get_user: {e}")
        return None

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        try:
            db = self._get_db()
            existing = await db["cl_users"].find_one({"identifier": user.identifier})
            if existing:
                return PersistedUser(
                    id=existing["id"],
                    identifier=existing["identifier"],
                    createdAt=existing.get("createdAt"),
                    metadata=existing.get("metadata", {}),
                    display_name=existing.get("display_name"),
                )

            user_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            user_doc = {
                "id": user_id,
                "identifier": user.identifier,
                "createdAt": created_at,
                "metadata": user.metadata or {},
                "display_name": getattr(user, "display_name", None),
            }
            await db["cl_users"].insert_one(user_doc)
            return PersistedUser(
                id=user_id,
                identifier=user.identifier,
                createdAt=created_at,
                metadata=user.metadata or {},
                display_name=getattr(user, "display_name", None),
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in create_user: {e}")
        return None
