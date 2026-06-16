import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from motor.motor_asyncio import AsyncIOMotorClient
from chainlit.data import BaseDataLayer
from chainlit.types import Pagination, ThreadFilter, PaginatedResponse, PageInfo, ThreadDict, Feedback, FeedbackDict
from chainlit.step import StepDict
from chainlit.element import Element, ElementDict
from chainlit.user import User, PersistedUser

logger = logging.getLogger(__name__)

DB_NAME = "personal_knowledge_ai"

class MongoDBDataLayer(BaseDataLayer):
    def __init__(self, mongo_uri: str = None):
        super().__init__()
        self._mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self._mongo_client = None
        self._db = None

    def _get_db(self):
        if self._mongo_client is None:
            try:
                self._mongo_client = AsyncIOMotorClient(self._mongo_uri, serverSelectionTimeoutMS=5000)
                self._db = self._mongo_client[DB_NAME]
            except Exception as e:
                logger.error(f"MongoDBDataLayer: Failed to connect to MongoDB: {e}")
                raise e
        return self._db

    def close(self):
        if self._mongo_client:
            self._mongo_client.close()
            self._mongo_client = None
            self._db = None

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
                    display_name=doc.get("display_name")
                )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in get_user: {e}")
        return None

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        try:
            db = self._get_db()
            # Return existing if found to avoid duplicates
            existing = await db["cl_users"].find_one({"identifier": user.identifier})
            if existing:
                return PersistedUser(
                    id=existing["id"],
                    identifier=existing["identifier"],
                    createdAt=existing.get("createdAt"),
                    metadata=existing.get("metadata", {}),
                    display_name=existing.get("display_name")
                )
            
            user_id = str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            user_doc = {
                "id": user_id,
                "identifier": user.identifier,
                "createdAt": created_at,
                "metadata": user.metadata or {},
                "display_name": getattr(user, "display_name", None)
            }
            await db["cl_users"].insert_one(user_doc)
            return PersistedUser(
                id=user_id,
                identifier=user.identifier,
                createdAt=created_at,
                metadata=user.metadata or {},
                display_name=getattr(user, "display_name", None)
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in create_user: {e}")
        return None

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        try:
            db = self._get_db()
            thread_doc = await db["cl_threads"].find_one({"id": thread_id})
            if not thread_doc:
                return None
            
            # Fetch steps sorted by createdAt
            steps_cursor = db["cl_steps"].find({"threadId": thread_id}).sort("createdAt", 1)
            steps = await steps_cursor.to_list(length=1000)
            
            # Fetch feedbacks and map to steps
            feedbacks_cursor = db["cl_feedbacks"].find({"threadId": thread_id})
            feedbacks = await feedbacks_cursor.to_list(length=1000)
            feedback_map = {fb["forId"]: fb for fb in feedbacks if "forId" in fb}
            
            steps_list = []
            for step in steps:
                step_id = step["id"]
                fb_doc = feedback_map.get(step_id)
                feedback_dict = None
                if fb_doc:
                    feedback_dict = FeedbackDict(
                        id=fb_doc["id"],
                        forId=step_id,
                        value=fb_doc["value"],
                        comment=fb_doc.get("comment")
                    )
                
                step_dict = StepDict(
                    id=step_id,
                    name=step["name"],
                    type=step["type"],
                    threadId=thread_id,
                    parentId=step.get("parentId"),
                    streaming=step.get("streaming", False),
                    waitForAnswer=step.get("waitForAnswer"),
                    isError=step.get("isError"),
                    metadata=step.get("metadata", {}),
                    tags=step.get("tags"),
                    input=step.get("input", ""),
                    output=step.get("output", ""),
                    createdAt=step.get("createdAt"),
                    start=step.get("start"),
                    end=step.get("end"),
                    generation=step.get("generation"),
                    showInput=step.get("showInput"),
                    language=step.get("language"),
                    feedback=feedback_dict
                )
                steps_list.append(step_dict)
            
            # Fetch elements
            elements_cursor = db["cl_elements"].find({"threadId": thread_id})
            elements = await elements_cursor.to_list(length=1000)
            elements_list = []
            for element in elements:
                el_url = element.get("url")
                # Plotly: serve stored content via our stable FastAPI endpoint
                if element.get("type") == "plotly" and not el_url and element.get("_plotly_content"):
                    el_url = f"/api/elements/{element['id']}/plotly"

                element_dict = ElementDict(
                    id=element["id"],
                    threadId=thread_id,
                    type=element["type"],
                    chainlitKey=element.get("chainlitKey"),
                    url=el_url,
                    objectKey=element.get("objectKey"),
                    name=element["name"],
                    display=element["display"],
                    size=element.get("size"),
                    language=element.get("language"),
                    autoPlay=element.get("autoPlay"),
                    playerConfig=element.get("playerConfig"),
                    page=element.get("page"),
                    props=element.get("props", {}),
                    forId=element.get("forId"),
                    mime=element.get("mime")
                )
                elements_list.append(element_dict)
            
            return ThreadDict(
                id=thread_id,
                createdAt=thread_doc.get("createdAt"),
                name=thread_doc.get("name"),
                userId=thread_doc.get("userId"),
                userIdentifier=thread_doc.get("userIdentifier"),
                tags=thread_doc.get("tags"),
                metadata=thread_doc.get("metadata", {}),
                steps=steps_list,
                elements=elements_list
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
            update_fields = {}
            if name is not None:
                update_fields["name"] = name
            if user_id is not None:
                update_fields["userId"] = user_id
            if metadata is not None:
                update_fields["metadata"] = metadata
            if tags is not None:
                update_fields["tags"] = tags
            
            on_insert_fields = {
                "id": thread_id,
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
            
            if user_id:
                user_doc = await db["cl_users"].find_one({"id": user_id})
                if user_doc:
                    update_fields["userIdentifier"] = user_doc["identifier"]
            
            await db["cl_threads"].update_one(
                {"id": thread_id},
                {
                    "$set": update_fields,
                    "$setOnInsert": on_insert_fields
                },
                upsert=True
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

    async def list_threads(self, pagination: Pagination, filters: ThreadFilter) -> PaginatedResponse[ThreadDict]:
        try:
            if not filters.userId:
                raise ValueError("userId is required")
            
            db = self._get_db()
            
            # Fetch user threads
            cursor = db["cl_threads"].find({"userId": filters.userId}).sort("createdAt", -1)
            user_threads = await cursor.to_list(length=1000)
            
            thread_ids = [t["id"] for t in user_threads]
            
            steps_list = []
            elements_list = []
            feedbacks_list = []
            if thread_ids:
                steps_cursor = db["cl_steps"].find({"threadId": {"$in": thread_ids}}).sort("createdAt", 1)
                steps_list = await steps_cursor.to_list(length=10000)
                
                elements_cursor = db["cl_elements"].find({"threadId": {"$in": thread_ids}})
                elements_list = await elements_cursor.to_list(length=10000)
                
                feedbacks_cursor = db["cl_feedbacks"].find({"threadId": {"$in": thread_ids}})
                feedbacks_list = await feedbacks_cursor.to_list(length=10000)
            
            from collections import defaultdict
            steps_by_thread = defaultdict(list)
            elements_by_thread = defaultdict(list)
            feedback_by_step = {fb["forId"]: fb for fb in feedbacks_list if "forId" in fb}
            
            for step in steps_list:
                step_id = step["id"]
                fb_doc = feedback_by_step.get(step_id)
                feedback_dict = None
                if fb_doc:
                    feedback_dict = FeedbackDict(
                        id=fb_doc["id"],
                        forId=step_id,
                        value=fb_doc["value"],
                        comment=fb_doc.get("comment")
                    )
                
                step_dict = StepDict(
                    id=step_id,
                    name=step["name"],
                    type=step["type"],
                    threadId=step["threadId"],
                    parentId=step.get("parentId"),
                    streaming=step.get("streaming", False),
                    waitForAnswer=step.get("waitForAnswer"),
                    isError=step.get("isError"),
                    metadata=step.get("metadata", {}),
                    tags=step.get("tags"),
                    input=step.get("input", ""),
                    output=step.get("output", ""),
                    createdAt=step.get("createdAt"),
                    start=step.get("start"),
                    end=step.get("end"),
                    generation=step.get("generation"),
                    showInput=step.get("showInput"),
                    language=step.get("language"),
                    feedback=feedback_dict
                )
                steps_by_thread[step["threadId"]].append(step_dict)
                
            for element in elements_list:
                element_dict = ElementDict(
                    id=element["id"],
                    threadId=element["threadId"],
                    type=element["type"],
                    chainlitKey=element.get("chainlitKey"),
                    url=element.get("url"),
                    objectKey=element.get("objectKey"),
                    name=element["name"],
                    display=element["display"],
                    size=element.get("size"),
                    language=element.get("language"),
                    autoPlay=element.get("autoPlay"),
                    playerConfig=element.get("playerConfig"),
                    page=element.get("page"),
                    props=element.get("props", {}),
                    forId=element.get("forId"),
                    mime=element.get("mime")
                )
                elements_by_thread[element["threadId"]].append(element_dict)
                
            all_threads = []
            for thread in user_threads:
                tid = thread["id"]
                all_threads.append(ThreadDict(
                    id=tid,
                    createdAt=thread.get("createdAt"),
                    name=thread.get("name"),
                    userId=thread.get("userId"),
                    userIdentifier=thread.get("userIdentifier"),
                    tags=thread.get("tags"),
                    metadata=thread.get("metadata", {}),
                    steps=steps_by_thread[tid],
                    elements=elements_by_thread[tid]
                ))
                
            search_keyword = filters.search.lower() if filters.search else None
            feedback_value = int(filters.feedback) if filters.feedback else None

            filtered_threads = []
            for thread in all_threads:
                keyword_match = True
                feedback_match = True
                if search_keyword or feedback_value is not None:
                    if search_keyword:
                        keyword_match = any(
                            search_keyword in step.get("output", "").lower()
                            for step in thread["steps"]
                        )
                    if feedback_value is not None:
                        feedback_match = False
                        for step in thread["steps"]:
                            fb = step.get("feedback")
                            if fb and fb.get("value") == feedback_value:
                                feedback_match = True
                                break
                if keyword_match and feedback_match:
                    filtered_threads.append(thread)

            # Slice for pagination
            start = 0
            if pagination.cursor:
                for i, thread in enumerate(filtered_threads):
                    if thread["id"] == pagination.cursor:
                        start = i + 1
                        break
            end = start + pagination.first
            paginated_threads = filtered_threads[start:end] or []

            has_next_page = len(filtered_threads) > end
            start_cursor = paginated_threads[0]["id"] if paginated_threads else None
            end_cursor = paginated_threads[-1]["id"] if paginated_threads else None

            return PaginatedResponse(
                pageInfo=PageInfo(
                    hasNextPage=has_next_page,
                    startCursor=start_cursor,
                    endCursor=end_cursor,
                ),
                data=paginated_threads,
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in list_threads: {e}")
            return PaginatedResponse(
                pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None),
                data=[]
            )

    async def create_step(self, step_dict: StepDict):
        try:
            db = self._get_db()
            await self.update_thread(step_dict["threadId"])
            
            if "showInput" in step_dict and step_dict["showInput"] is not None:
                step_dict["showInput"] = str(step_dict["showInput"]).lower()
            
            doc = dict(step_dict)
            doc["_id"] = doc["id"]
            
            await db["cl_steps"].replace_one(
                {"id": doc["id"]},
                doc,
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in create_step: {e}")

    async def update_step(self, step_dict: StepDict):
        try:
            db = self._get_db()
            if "showInput" in step_dict and step_dict["showInput"] is not None:
                step_dict["showInput"] = str(step_dict["showInput"]).lower()
            
            doc = dict(step_dict)
            doc["_id"] = doc["id"]
            
            await db["cl_steps"].replace_one(
                {"id": doc["id"]},
                doc,
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in update_step: {e}")

    async def delete_step(self, step_id: str):
        try:
            db = self._get_db()
            await db["cl_steps"].delete_one({"id": step_id})
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in delete_step: {e}")

    async def create_element(self, element: Element):
        try:
            db = self._get_db()
            doc = element.to_dict()
            doc["_id"] = doc["id"]

            # cl.Plotly stores the figure JSON in element.content (not in ElementDict).
            # File storage is not configured, so we save it directly in the document
            # and serve it back via /api/elements/{id}/plotly on reload.
            if getattr(element, "type", None) == "plotly":
                content = getattr(element, "content", None)
                if content:
                    doc["_plotly_content"] = content if isinstance(content, str) else content.decode()

            await db["cl_elements"].replace_one(
                {"id": doc["id"]},
                doc,
                upsert=True
            )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in create_element: {e}")

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        try:
            db = self._get_db()
            query = {"id": element_id}
            if thread_id:
                query["threadId"] = thread_id
            await db["cl_elements"].delete_one(query)
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in delete_element: {e}")

    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        try:
            db = self._get_db()
            doc = await db["cl_elements"].find_one({"threadId": thread_id, "id": element_id})
            if doc:
                return ElementDict(
                    id=doc["id"],
                    threadId=doc.get("threadId"),
                    type=doc["type"],
                    chainlitKey=doc.get("chainlitKey"),
                    url=doc.get("url"),
                    objectKey=doc.get("objectKey"),
                    name=doc["name"],
                    display=doc["display"],
                    size=doc.get("size"),
                    language=doc.get("language"),
                    autoPlay=doc.get("autoPlay"),
                    playerConfig=doc.get("playerConfig"),
                    page=doc.get("page"),
                    props=doc.get("props", {}),
                    forId=doc.get("forId"),
                    mime=doc.get("mime")
                )
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in get_element: {e}")
        return None

    async def upsert_feedback(self, feedback: Feedback) -> str:
        try:
            db = self._get_db()
            fb_id = feedback.id or str(uuid.uuid4())
            doc = {
                "id": fb_id,
                "forId": feedback.forId,
                "value": feedback.value,
                "threadId": feedback.threadId,
                "comment": feedback.comment
            }
            doc["_id"] = fb_id
            
            await db["cl_feedbacks"].replace_one(
                {"id": fb_id},
                doc,
                upsert=True
            )
            return fb_id
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in upsert_feedback: {e}")
            return feedback.id or ""

    async def delete_feedback(self, feedback_id: str) -> bool:
        try:
            db = self._get_db()
            res = await db["cl_feedbacks"].delete_one({"id": feedback_id})
            return res.deleted_count > 0
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in delete_feedback: {e}")
            return False

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        return []

    async def set_step_favorite(self, step_dict: StepDict, favorite: bool) -> StepDict:
        return step_dict

    async def get_thread_author(self, thread_id: str) -> str:
        try:
            db = self._get_db()
            thread = await db["cl_threads"].find_one({"id": thread_id})
            if thread:
                return thread.get("userIdentifier", "Guest")
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in get_thread_author: {e}")
        return "Guest"

    def build_debug_url(self) -> str:
        return ""
