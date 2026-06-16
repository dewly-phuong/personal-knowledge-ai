import os
import unittest
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.memory.session_store import SessionStore
from app.memory.summary_buffer import compress_history, _to_turns
from app.memory.history_manager import HistoryManager


# Helper for running async test methods
def async_test(coro):
    def wrapper(*args, **kwargs):
        return asyncio.run(coro(*args, **kwargs))

    return wrapper


class TestMemorySystem(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.session_id = "test-session-12345"
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.store = SessionStore(mongo_uri=self.mongo_uri)
        self.manager = HistoryManager(store=self.store)

    def tearDown(self):
        # Reset the mongo client to avoid event loop binding issues across loops
        self.store._mongo_client = None

        # Clean up test session and flush background tasks
        async def cleanup():
            await self.store.clear(self.session_id)
            await self.store.flush()

        asyncio.run(cleanup())
        self.store.close()

    def test_to_turns(self):
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there"),
            HumanMessage(content="What is a service?"),
            AIMessage(content="A service is a deployment unit."),
        ]
        turns = _to_turns(messages)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0]["human"], "Hello")
        self.assertEqual(turns[0]["ai"], "Hi there")
        self.assertEqual(turns[1]["human"], "What is a service?")
        self.assertEqual(turns[1]["ai"], "A service is a deployment unit.")

    @async_test
    async def test_session_store_save_and_load(self):
        messages = [
            HumanMessage(content="Ping"),
            AIMessage(content="Pong"),
        ]
        # Save messages
        await self.store.save(self.session_id, messages)
        await self.store.flush()

        # Load and verify
        loaded = await self.store.load(self.session_id)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].content, "Ping")
        self.assertEqual(loaded[1].content, "Pong")

    @async_test
    async def test_session_store_clear(self):
        messages = [HumanMessage(content="Test clear")]
        await self.store.save(self.session_id, messages)
        await self.store.flush()

        # Verify saved
        loaded = await self.store.load(self.session_id)
        self.assertEqual(len(loaded), 1)

        # Clear session
        await self.store.clear(self.session_id)
        await self.store.flush()

        # Verify cleared
        loaded = await self.store.load(self.session_id)
        self.assertEqual(loaded, [])

    @async_test
    async def test_compress_history_under_limit(self):
        # 2 turns is under 3 turns limit
        messages = [
            HumanMessage(content="T1"),
            AIMessage(content="R1"),
            HumanMessage(content="T2"),
            AIMessage(content="R2"),
        ]
        compressed = await compress_history(messages, max_recent=3)
        self.assertEqual(len(compressed), 4)
        self.assertEqual(compressed, messages)

    @async_test
    async def test_compress_history_over_limit(self):
        # 4 turns exceeds 3 turns limit
        messages = [
            HumanMessage(content="Hỏi về service A"),
            AIMessage(content="Service A có owner là team platform"),
            HumanMessage(content="Hỏi về service B"),
            AIMessage(content="Service B có owner là team billing"),
            HumanMessage(content="Hỏi về service C"),
            AIMessage(content="Service C có owner là team logistics"),
            HumanMessage(content="Hỏi về service D"),
            AIMessage(content="Service D có owner là team ops"),
        ]

        # We perform compression. It should use Gemini Flash to summarize the first turn.
        # Since this calls real Gemini API, we wrap it in a try-except in case GOOGLE_API_KEY is missing/invalid.
        google_key = os.getenv("GOOGLE_API_KEY")
        if not google_key:
            self.skipTest("GOOGLE_API_KEY not found in .env")

        try:
            compressed = await compress_history(messages, max_recent=3)
            # Should have: 1 SystemMessage (summary) + 6 messages (3 recent turns) = 7 messages total
            self.assertEqual(len(compressed), 7)
            self.assertTrue(isinstance(compressed[0], SystemMessage))
            self.assertTrue("[Tóm tắt hội thoại trước]" in compressed[0].content)
            self.assertEqual(compressed[1].content, "Hỏi về service B")
            self.assertEqual(compressed[-1].content, "Service D có owner là team ops")
        except Exception as e:
            self.fail(f"History compression failed with error: {e}")

    @async_test
    async def test_history_manager_flow(self):
        # Test full flow via manager
        await self.manager.append_turn(self.session_id, "User Q1", "Agent A1")
        await self.store.flush()

        # Load context
        context = await self.manager.get_context(self.session_id)
        self.assertEqual(len(context), 2)
        self.assertEqual(context[0].content, "User Q1")
        self.assertEqual(context[1].content, "Agent A1")

    @async_test
    async def test_history_manager_with_tools(self):
        from langchain_core.agents import AgentAction
        from langchain_core.messages import AIMessage, ToolMessage

        action = AgentAction(
            tool="wiki_search",
            tool_input="knowledge graph",
            log="Calling wiki_search...",
        )
        object.__setattr__(
            action,
            "message_log",
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "wiki_search",
                            "args": {"query": "knowledge graph"},
                            "id": "call_1",
                        }
                    ],
                )
            ],
        )

        intermediate_steps = [(action, "Wiki results content")]

        await self.manager.append_turn(
            self.session_id,
            "Explain knowledge graph",
            "A knowledge graph is...",
            intermediate_steps,
        )
        await self.store.flush()

        context = await self.manager.get_context(self.session_id)
        self.assertEqual(len(context), 4)
        self.assertEqual(context[0].content, "Explain knowledge graph")

        self.assertTrue(isinstance(context[1], AIMessage))
        self.assertEqual(context[1].tool_calls[0]["name"], "wiki_search")
        self.assertEqual(context[1].tool_calls[0]["id"], "call_1")

        self.assertTrue(isinstance(context[2], ToolMessage))
        self.assertEqual(context[2].content, "Wiki results content")
        self.assertEqual(context[2].tool_call_id, "call_1")

        self.assertEqual(context[3].content, "A knowledge graph is...")


if __name__ == "__main__":
    unittest.main()
