import os
import unittest
import asyncio
import uuid
from dotenv import load_dotenv
from app.memory.mongodb_data_layer import MongoDBDataLayer
from chainlit.user import User
from chainlit.step import StepDict
from chainlit.types import Pagination, ThreadFilter, Feedback


# Helper for running async test methods
def async_test(coro):
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))

    return wrapper


class TestMongoDBDataLayer(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

        from pymongo import MongoClient
        from pymongo.errors import ServerSelectionTimeoutError

        try:
            _c = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2000)
            _c.admin.command("ping")
            _c.close()
        except Exception:
            raise unittest.SkipTest("MongoDB not available — skipping data layer tests")

        self.data_layer = MongoDBDataLayer(mongo_uri=self.mongo_uri)
        self.test_user_id = str(uuid.uuid4())
        self.test_username = f"test-user-{uuid.uuid4().hex[:8]}"
        self.test_thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"

    def tearDown(self):
        # Reset the mongo client to avoid event loop binding issues across loops
        self.data_layer.close()

        # Clean up test data asynchronously
        async def cleanup():
            db = self.data_layer._get_db()
            await db["cl_users"].delete_many({"identifier": self.test_username})
            await db["cl_threads"].delete_many({"id": self.test_thread_id})
            await db["cl_steps"].delete_many({"threadId": self.test_thread_id})
            await db["cl_elements"].delete_many({"threadId": self.test_thread_id})
            await db["cl_feedbacks"].delete_many({"threadId": self.test_thread_id})

        asyncio.run(cleanup())
        self.data_layer.close()

    @async_test
    async def test_user_lifecycle(self):
        # 1. Get user should return None initially
        user = await self.data_layer.get_user(self.test_username)
        self.assertIsNone(user)

        # 2. Create user
        new_user = User(identifier=self.test_username, metadata={"role": "TEST"})
        persisted = await self.data_layer.create_user(new_user)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.identifier, self.test_username)
        self.assertEqual(persisted.metadata.get("role"), "TEST")
        self.assertTrue(hasattr(persisted, "id"))

        # 3. Get user should now succeed
        loaded = await self.data_layer.get_user(self.test_username)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, persisted.id)
        self.assertEqual(loaded.identifier, self.test_username)

    @async_test
    async def test_thread_and_step_lifecycle(self):
        # Setup test user first
        user = User(identifier=self.test_username, metadata={})
        persisted_user = await self.data_layer.create_user(user)

        # 1. Update/insert thread
        await self.data_layer.update_thread(
            thread_id=self.test_thread_id,
            name="Test Thread",
            user_id=persisted_user.id,
            metadata={"source": "test"},
            tags=["unit-test"],
        )

        # Verify thread metadata
        thread = await self.data_layer.get_thread(self.test_thread_id)
        self.assertIsNotNone(thread)
        self.assertEqual(thread["name"], "Test Thread")
        self.assertEqual(thread["userId"], persisted_user.id)
        self.assertEqual(thread["userIdentifier"], self.test_username)
        self.assertEqual(thread["tags"], ["unit-test"])

        # 2. Create steps
        step1_id = str(uuid.uuid4())
        step1 = StepDict(
            id=step1_id,
            threadId=self.test_thread_id,
            name="User Message",
            type="user_message",
            input="Hello",
            output="Hello Output",
            createdAt="2026-06-12T12:00:00Z",
        )
        await self.data_layer.create_step(step1)

        step2_id = str(uuid.uuid4())
        step2 = StepDict(
            id=step2_id,
            threadId=self.test_thread_id,
            name="Assistant Message",
            type="assistant_message",
            input="Hello Output",
            output="Response!",
            createdAt="2026-06-12T12:01:00Z",
        )
        await self.data_layer.create_step(step2)

        # Get thread and verify steps are loaded and sorted
        thread_with_steps = await self.data_layer.get_thread(self.test_thread_id)
        self.assertEqual(len(thread_with_steps["steps"]), 2)
        self.assertEqual(thread_with_steps["steps"][0]["id"], step1_id)
        self.assertEqual(thread_with_steps["steps"][1]["id"], step2_id)

        # 3. List threads with filters
        pagination = Pagination(first=10, cursor=None)
        filters = ThreadFilter(userId=persisted_user.id, search=None, feedback=None)
        res = await self.data_layer.list_threads(pagination, filters)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["id"], self.test_thread_id)

        # 4. Delete thread
        await self.data_layer.delete_thread(self.test_thread_id)
        deleted_thread = await self.data_layer.get_thread(self.test_thread_id)
        self.assertIsNone(deleted_thread)

        # Verify steps were also deleted
        db = self.data_layer._get_db()
        remaining_steps = await db["cl_steps"].count_documents(
            {"threadId": self.test_thread_id}
        )
        self.assertEqual(remaining_steps, 0)

    @async_test
    async def test_feedback_lifecycle(self):
        # 1. Upsert feedback
        fb = Feedback(
            forId="some-step-id",
            value=1,
            threadId=self.test_thread_id,
            comment="Excellent response",
        )
        fb_id = await self.data_layer.upsert_feedback(fb)
        self.assertTrue(len(fb_id) > 0)

        # Verify feedback in db
        db = self.data_layer._get_db()
        doc = await db["cl_feedbacks"].find_one({"id": fb_id})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["value"], 1)
        self.assertEqual(doc["comment"], "Excellent response")

        # 2. Delete feedback
        deleted = await self.data_layer.delete_feedback(fb_id)
        self.assertTrue(deleted)
        doc_after = await db["cl_feedbacks"].find_one({"id": fb_id})
        self.assertIsNone(doc_after)


if __name__ == "__main__":
    unittest.main()
