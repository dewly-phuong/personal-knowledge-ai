import os
import unittest
from unittest.mock import patch

from dotenv import load_dotenv

import app.tools as public_tools
from app.agent import SYSTEM_PROMPT, create_conversational_agent, get_llm


class TestAgent(unittest.TestCase):
    def setUp(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")

    def test_system_prompt_is_general(self):
        self.assertIn("knowledge_search", SYSTEM_PROMPT)
        self.assertNotIn("payroll_september_2024", SYSTEM_PROMPT)
        self.assertNotIn("attendance_october_2024", SYSTEM_PROMPT)
        self.assertNotIn("revenue_2024", SYSTEM_PROMPT)
        self.assertNotIn("infrastructure_costs_sep2024", SYSTEM_PROMPT)
        self.assertNotIn("filter_json", SYSTEM_PROMPT)

    def test_system_prompt_enforces_strict_factual_mode(self):
        self.assertIn("Strict factual mode", SYSTEM_PROMPT)
        self.assertIn("directly supported by an ok tool result", SYSTEM_PROMPT)
        self.assertIn("do not answer from general knowledge", SYSTEM_PROMPT)
        self.assertIn("If no relevant data is available", SYSTEM_PROMPT)
        self.assertIn("Không có dữ liệu liên quan", SYSTEM_PROMPT)

    def test_system_prompt_includes_general_anti_hallucination_rules(self):
        self.assertIn("Do not guess", SYSTEM_PROMPT)
        self.assertIn("Do not merge facts from different sources", SYSTEM_PROMPT)
        self.assertIn(
            "Do not treat examples, schemas, or field names as actual data",
            SYSTEM_PROMPT,
        )
        self.assertIn("Separate evidence from interpretation", SYSTEM_PROMPT)

    @patch("app.agent.ChatGoogleGenerativeAI")
    def test_llm_defaults_to_strict_temperature(self, mock_llm):
        get_llm()

        self.assertEqual(mock_llm.call_args.kwargs["temperature"], 0)

    @patch("app.agent.create_agent")
    @patch("app.agent.ChatGoogleGenerativeAI")
    def test_agent_defaults_to_strict_temperature(self, mock_llm, mock_create_agent):
        mock_create_agent.return_value.with_config.return_value = "agent"

        create_conversational_agent()

        self.assertEqual(mock_llm.call_args.kwargs["temperature"], 0)

    @patch("app.agent.create_agent")
    @patch("app.agent.ChatGoogleGenerativeAI")
    def test_agent_preserves_explicit_temperature(self, mock_llm, mock_create_agent):
        mock_create_agent.return_value.with_config.return_value = "agent"

        create_conversational_agent(temperature=0.3)

        self.assertEqual(mock_llm.call_args.kwargs["temperature"], 0.3)

    @patch("app.agent.create_agent")
    @patch("app.agent.ChatGoogleGenerativeAI")
    def test_agent_uses_supplied_system_prompt(self, mock_llm, mock_create_agent):
        mock_create_agent.return_value.with_config.return_value = "agent"

        agent = create_conversational_agent(system_prompt="custom prompt")

        self.assertEqual(agent, "agent")
        self.assertEqual(
            mock_create_agent.call_args.kwargs["system_prompt"], "custom prompt"
        )

    @patch("app.agent.create_agent")
    @patch("app.agent.ChatGoogleGenerativeAI")
    def test_agent_exposes_small_tool_surface(self, mock_llm, mock_create_agent):
        mock_create_agent.return_value.with_config.return_value = "agent"

        create_conversational_agent()

        tool_names = [tool.name for tool in mock_create_agent.call_args.kwargs["tools"]]
        self.assertEqual(tool_names, ["knowledge_search", "generate_chart"])

    def test_public_tool_registry_only_exposes_agent_tools(self):
        self.assertEqual(public_tools.__all__, ["knowledge_search", "generate_chart"])
        self.assertFalse(hasattr(public_tools, "graph_traverse"))
        self.assertFalse(hasattr(public_tools, "uploaded_file_context"))
        self.assertFalse(hasattr(public_tools, "mongodb_query"))

    def test_multihop_queries(self):
        """Optional live smoke test for the deployed model and local knowledge base."""
        if not self.api_key or os.getenv("RUN_LIVE_AGENT_TESTS") != "1":
            self.skipTest(
                "Set GOOGLE_API_KEY and RUN_LIVE_AGENT_TESTS=1 to run live agent eval."
            )

        agent = create_conversational_agent()
        from langchain_core.messages import HumanMessage

        result = agent.invoke(
            {"messages": [HumanMessage(content="Auth-service liên quan gì?")]}
        )
        msgs = result.get("messages", [])
        last = msgs[-1] if msgs else None
        output = getattr(last, "content", "") or ""
        if isinstance(output, list):
            output = " ".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in output
            )

        self.assertIsNotNone(output)
        self.assertTrue(len(output) > 0)


if __name__ == "__main__":
    unittest.main()
