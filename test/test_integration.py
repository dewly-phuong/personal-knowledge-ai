import unittest
import os
from dotenv import load_dotenv


class TestGeminiIntegration(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")

    def test_tool_calling(self):
        """Test if the agent can correctly call a tool."""
        if not self.api_key:
            self.skipTest("GOOGLE_API_KEY not found in .env")

        from app.agent import create_conversational_agent

        agent = create_conversational_agent()

        try:
            # Ask a question that requires the get_current_time tool
            from langchain_core.messages import HumanMessage

            result = agent.invoke(
                {"messages": [HumanMessage(content="What time is it?")]}
            )
            msgs = result.get("messages", [])
            last = msgs[-1] if msgs else None
            output = getattr(last, "content", "") or ""
            if isinstance(output, list):
                output = " ".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in output
                )
            print(f"\n[Integration Test] Tool Call Success. Output: {output}")
            self.assertIsNotNone(output)
            self.assertTrue(len(output) > 0)
        except Exception as e:
            self.fail(f"Agent failed to call tool. Error: {e}")


if __name__ == "__main__":
    unittest.main()
