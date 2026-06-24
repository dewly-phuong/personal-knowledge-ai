import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from chainlit.types import (
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)

from app.memory._mappers import artifact_to_element, doc_to_element, doc_to_step
from app.memory.mongodb_thread_filters import filter_threads, paginate

logger = logging.getLogger(__name__)


class MongoThreadMixin:
    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        try:
            db = self._get_db()
            thread_doc = await db["cl_threads"].find_one({"id": thread_id})
            if not thread_doc:
                return None
            steps_raw = await _list(
                db["cl_steps"].find({"threadId": thread_id}).sort("createdAt", 1)
            )
            feedbacks_raw = await _list(
                db["cl_feedbacks"].find({"threadId": thread_id})
            )
            feedback_map = {fb["forId"]: fb for fb in feedbacks_raw if "forId" in fb}
            elements_raw = await _list(db["cl_elements"].find({"threadId": thread_id}))
            element_ids = {e.get("id") for e in elements_raw}
            elements = [doc_to_element(e, thread_id) for e in elements_raw]
            elements.extend(await _upload_elements(db, thread_id, element_ids))
            return _thread_dict(
                thread_doc,
                steps=[doc_to_step(s, feedback_map) for s in steps_raw],
                elements=elements,
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in get_thread: {e}")
        return None

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        try:
            db = self._get_db()
            update_fields = _thread_update_fields(name, user_id, metadata, tags)
            if user_id:
                user_doc = await db["cl_users"].find_one({"id": user_id})
                if user_doc:
                    update_fields["userIdentifier"] = user_doc["identifier"]
            await db["cl_threads"].update_one(
                {"id": thread_id},
                {
                    "$set": update_fields,
                    "$setOnInsert": {
                        "id": thread_id,
                        "createdAt": datetime.now(timezone.utc).isoformat(),
                    },
                },
                upsert=True,
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in update_thread: {e}")

    async def delete_thread(self, thread_id: str):
        try:
            db = self._get_db()
            await db["cl_threads"].delete_one({"id": thread_id})
            await db["cl_steps"].delete_many({"threadId": thread_id})
            await db["cl_elements"].delete_many({"threadId": thread_id})
            await db["cl_feedbacks"].delete_many({"threadId": thread_id})
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in delete_thread: {e}")

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        try:
            if not filters.userId:
                raise ValueError("userId is required")
            db = self._get_db()
            user_threads = await _list(
                db["cl_threads"].find({"userId": filters.userId}).sort("createdAt", -1)
            )
            threads = await _hydrate_threads(db, user_threads)
            paginated, has_next = paginate(filter_threads(threads, filters), pagination)
            return PaginatedResponse(
                pageInfo=PageInfo(
                    hasNextPage=has_next,
                    startCursor=paginated[0]["id"] if paginated else None,
                    endCursor=paginated[-1]["id"] if paginated else None,
                ),
                data=paginated,
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in list_threads: {e}")
            return PaginatedResponse(
                pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None),
                data=[],
            )

    async def get_thread_author(self, thread_id: str) -> str:
        try:
            thread = await self._get_db()["cl_threads"].find_one({"id": thread_id})
            if thread:
                return thread.get("userIdentifier", "Guest")
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in get_thread_author: {e}")
        return "Guest"


async def _list(cursor, length: int = 1000):
    return await cursor.to_list(length=length)


async def _upload_elements(db, thread_id: str, element_ids: set) -> list:
    artifacts = await _list(
        db["uploaded_artifacts"].find({"session_id": thread_id, "status": "processed"})
    )
    return [
        artifact_to_element(artifact, thread_id)
        for artifact in artifacts
        if f"upload-{artifact['upload_id']}" not in element_ids
    ]


async def _hydrate_threads(db, user_threads: list) -> list[ThreadDict]:
    thread_ids = [t["id"] for t in user_threads]
    steps_list = elements_list = feedbacks_list = []
    if thread_ids:
        steps_list = await _list(
            db["cl_steps"].find({"threadId": {"$in": thread_ids}}).sort("createdAt", 1),
            length=10000,
        )
        elements_list = await _list(
            db["cl_elements"].find({"threadId": {"$in": thread_ids}}), length=10000
        )
        feedbacks_list = await _list(
            db["cl_feedbacks"].find({"threadId": {"$in": thread_ids}}), length=10000
        )
    feedback_map = {fb["forId"]: fb for fb in feedbacks_list if "forId" in fb}
    steps_by_thread, elements_by_thread = defaultdict(list), defaultdict(list)
    for step in steps_list:
        steps_by_thread[step["threadId"]].append(doc_to_step(step, feedback_map))
    for element in elements_list:
        elements_by_thread[element["threadId"]].append(doc_to_element(element))
    return [
        _thread_dict(t, steps_by_thread[t["id"]], elements_by_thread[t["id"]])
        for t in user_threads
    ]


def _thread_dict(doc, steps, elements) -> ThreadDict:
    return ThreadDict(
        id=doc["id"],
        createdAt=doc.get("createdAt"),
        name=doc.get("name"),
        userId=doc.get("userId"),
        userIdentifier=doc.get("userIdentifier"),
        tags=doc.get("tags"),
        metadata=doc.get("metadata", {}),
        steps=steps,
        elements=elements,
    )


def _thread_update_fields(name, user_id, metadata, tags) -> Dict:
    return {
        key: value
        for key, value in {
            "name": name,
            "userId": user_id,
            "metadata": metadata,
            "tags": tags,
        }.items()
        if value is not None
    }
