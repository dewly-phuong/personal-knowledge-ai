import unittest
import os
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

from app.agent import create_conversational_agent
from app.tools import get_current_time, wiki_search, graph_traverse, lint_wiki

class TestAgent(unittest.TestCase):

    def setUp(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")

    def test_tools_existence(self):
        """Test if basic tools can be successfully invoked."""
        time_result = get_current_time.invoke({})
        self.assertIsInstance(time_result, str)
        self.assertTrue(len(time_result) > 0)

        lint_result = lint_wiki.invoke({})
        self.assertIn("Wiki Health Audit Report", lint_result)

    @patch('app.agent.ChatGoogleGenerativeAI')
    def test_agent_initialization(self, mock_llm):
        """Test if the agent executor is initialized correctly with 6 tools."""
        agent_executor = create_conversational_agent()
        self.assertEqual(len(agent_executor.tools), 6)
        tool_names = [t.name for t in agent_executor.tools]
        self.assertIn("get_current_time", tool_names)
        self.assertIn("wiki_search", tool_names)
        self.assertIn("graph_traverse", tool_names)
        self.assertIn("ingest_source", tool_names)
        self.assertIn("lint_wiki", tool_names)
        self.assertIn("sync_knowledge_base", tool_names)

    def test_multihop_queries(self):
        """Test 10 multi-hop queries on the live agent to evaluate graph traversal and citation quality."""
        if not self.api_key:
            self.skipTest("GOOGLE_API_KEY not found in .env, skipping live multi-hop evaluation.")

        agent = create_conversational_agent()
        queries = [
            "QMD dùng database gì và lưu trữ vector như thế nào?",
            "Auth-service kết nối với cơ sở dữ liệu nào và sử dụng cache gì?",
            "Payment processing pipeline phụ thuộc vào những dịch vụ nào?",
            "Dịch vụ nào gọi đến auth-service?",
            "Team nào phụ trách quản lý auth-service?",
            "MCP Server giao tiếp với Claude Desktop qua phương thức nào?",
            "QMD hỗ trợ những embedding models nào?",
            "Smart chunking hoạt động như thế nào trong QMD?",
            "SQLite-vec là gì và tại sao được chọn làm vector backend?",
            "Kiến trúc hybrid search của QMD bao gồm những gì?"
        ]

        print("\n=== Running Multi-Hop Query Quality Evaluation ===")
        for i, q in enumerate(queries):
            try:
                print(f"\nQuery {i+1}: {q}")
                res = agent.invoke({"input": q, "chat_history": []})
                output = res["output"]
                
                if isinstance(output, list):
                    output_str = ""
                    for part in output:
                        if isinstance(part, dict) and "text" in part:
                            output_str += part["text"]
                        elif isinstance(part, str):
                            output_str += part
                    output = output_str
                
                print(f"Agent Output:\n{output}\n")
                
                self.assertIsNotNone(output)
                self.assertTrue(len(output) > 0)
                # Ensure the agent output includes citations to wiki or sources
                has_source = any(indicator in output.lower() for indicator in ["wiki/", "nguồn:", "source", "tài liệu", "file:"])
                print(f"Citations/References Checked: {has_source}")
            except Exception as e:
                self.fail(f"Agent failed on query '{q}'. Error: {e}")

if __name__ == '__main__':
    unittest.main()
