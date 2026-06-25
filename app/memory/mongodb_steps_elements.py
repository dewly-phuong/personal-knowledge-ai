import logging
import os
from typing import Optional

from chainlit.element import Element, ElementDict
from chainlit.step import StepDict

from app.memory._mappers import doc_to_element

logger = logging.getLogger(__name__)


class MongoStepElementMixin:
    async def create_step(self, step_dict: StepDict):
        try:
            db = self._get_db()
            await self.update_thread(step_dict["threadId"])
            doc = _step_doc(step_dict)
            await db["cl_steps"].replace_one({"_id": doc["_id"]}, doc, upsert=True)
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in create_step: {e}")

    async def update_step(self, step_dict: StepDict):
        try:
            db = self._get_db()
            doc = _step_doc(step_dict)
            await db["cl_steps"].replace_one({"_id": doc["_id"]}, doc, upsert=True)
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in update_step: {e}")

    async def delete_step(self, step_id: str):
        try:
            await self._get_db()["cl_steps"].delete_one({"id": step_id})
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in delete_step: {e}")

    async def create_element(self, element: Element):
        try:
            db = self._get_db()
            doc = element.to_dict()
            doc["_id"] = doc["id"]
            _attach_element_content(doc, element)
            await db["cl_elements"].replace_one({"_id": doc["_id"]}, doc, upsert=True)
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in create_element: {e}")

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        try:
            query = {"id": element_id}
            if thread_id:
                query["threadId"] = thread_id
            await self._get_db()["cl_elements"].delete_one(query)
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in delete_element: {e}")

    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional[ElementDict]:
        try:
            doc = await self._get_db()["cl_elements"].find_one(
                {"threadId": thread_id, "id": element_id}
            )
            if doc:
                return doc_to_element(doc, thread_id)
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in get_element: {e}")
        return None


def _step_doc(step_dict: StepDict) -> dict:
    if "showInput" in step_dict and step_dict["showInput"] is not None:
        step_dict["showInput"] = str(step_dict["showInput"]).lower()
    doc = dict(step_dict)
    doc["_id"] = doc["id"]
    return doc


def _attach_element_content(doc: dict, element: Element) -> None:
    if getattr(element, "type", None) == "plotly":
        content = getattr(element, "content", None)
        if content:
            doc["_plotly_content"] = (
                content if isinstance(content, str) else content.decode()
            )
        return
    if getattr(element, "type", None) != "file":
        return
    content = _file_content(element)
    if content is not None:
        doc["_file_content"] = (
            content.encode("utf-8") if isinstance(content, str) else content
        )
        doc["_file_mime"] = getattr(element, "mime", None)


def _file_content(element: Element):
    content = getattr(element, "content", None)
    path = getattr(element, "path", None)
    if content is None and path and os.path.exists(path):
        max_bytes = 8 * 1024 * 1024
        if os.path.getsize(path) <= max_bytes:
            with open(path, "rb") as f:
                return f.read()
    return content
