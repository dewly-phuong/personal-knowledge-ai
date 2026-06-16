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
            response = agent.invoke({"input": "What time is it?", "chat_history": []})
            output = response["output"]
            print(f"\n[Integration Test] Tool Call Success. Output: {output}")
            self.assertIsNotNone(output)
        except Exception as e:
            self.fail(f"Agent failed to call tool. Error: {e}")


if __name__ == "__main__":
    unittest.main()
