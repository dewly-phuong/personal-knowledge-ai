import logging
import uuid
from typing import List

from chainlit.step import StepDict
from chainlit.types import Feedback

logger = logging.getLogger(__name__)


class MongoFeedbackMixin:
    async def upsert_feedback(self, feedback: Feedback) -> str:
        try:
            db = self._get_db()
            fb_id = feedback.id or str(uuid.uuid4())
            doc = {
                "id": fb_id,
                "_id": fb_id,
                "forId": feedback.forId,
                "value": feedback.value,
                "threadId": feedback.threadId,
                "comment": feedback.comment,
            }
            await db["cl_feedbacks"].replace_one({"id": fb_id}, doc, upsert=True)
            return fb_id
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in upsert_feedback: {e}")
            return feedback.id or ""

    async def delete_feedback(self, feedback_id: str) -> bool:
        try:
            res = await self._get_db()["cl_feedbacks"].delete_one({"id": feedback_id})
            return res.deleted_count > 0
        except Exception as e:
            logger.error(f"MongoDBDataLayer: Error in delete_feedback: {e}")
            return False

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        return []

    async def set_step_favorite(self, step_dict: StepDict, favorite: bool) -> StepDict:
        return step_dict

    def build_debug_url(self) -> str:
        return ""
