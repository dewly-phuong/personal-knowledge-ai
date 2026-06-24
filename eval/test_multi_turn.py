"""
Multi-turn end-to-end evaluation.

Tải các cuộc hội thoại đã được mô phỏng sẵn từ eval/datasets/multi_turn_goldens.json
(được tạo bởi ConversationSimulator trong generate_datasets.py) và đánh giá trực tiếp.

Metrics (tối đa 5, theo chiến lược Agent + RAG + Graph chatbot):
  --- Turn-level ---
  1. AnswerRelevancyMetric          — output có trả lời đúng câu hỏi không
  2. FaithfulnessMetric             — output có trung thực với context không
  3. ToolCorrectnessMetric          — tool được gọi có đúng expected_tools không

  --- Conversation-level ---
  4. ConversationCompletenessMetric — hội thoại có đáp ứng đủ nhu cầu không
  5. KnowledgeRetentionMetric       — agent có nhớ ngữ cảnh từ các lượt trước không

Prerequisites:
    uv run python eval/generate_datasets.py

Run:
    uv run pytest eval/test_multi_turn.py -v
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ConversationCompletenessMetric,
    FaithfulnessMetric,
    KnowledgeRetentionMetric,
    ToolCorrectnessMetric,
)
from deepeval.test_case import ConversationalTestCase, LLMTestCase, Turn
from deepeval.test_case.llm_test_case import ToolCall

from eval.judge import GeminiJudge

load_dotenv()

DATASET_PATH = Path(__file__).parent / "datasets" / "multi_turn_goldens.json"

_judge = GeminiJudge()

# ---------------------------------------------------------------------------
# Metrics — turn-level
# ---------------------------------------------------------------------------

_answer_relevancy = AnswerRelevancyMetric(threshold=0.5, model=_judge, async_mode=False)

_faithfulness = FaithfulnessMetric(threshold=0.5, model=_judge, async_mode=False)

_tool_correctness = ToolCorrectnessMetric(threshold=0.5, model=_judge)

# ---------------------------------------------------------------------------
# Metrics — conversation-level
# ---------------------------------------------------------------------------

_completeness = ConversationCompletenessMetric(
    threshold=0.5, model=_judge, async_mode=False
)

_knowledge_retention = KnowledgeRetentionMetric(
    threshold=0.5, model=_judge, async_mode=False
)

_CONVERSATION_METRICS = [
    _completeness,
    _knowledge_retention,
]

# ---------------------------------------------------------------------------
# Load pre-simulated conversations from dataset
# ---------------------------------------------------------------------------


def _load_records() -> list[dict[str, Any]]:
    if not DATASET_PATH.exists():
        return []
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _tool_calls(items: list[dict[str, Any]] | None) -> list[ToolCall]:
    return [ToolCall(name=item["name"]) for item in (items or []) if item.get("name")]


def _conversation_case(record: dict[str, Any]) -> ConversationalTestCase:
    turns = [
        Turn(
            role=t["role"],
            content=t["content"],
            retrieval_context=t.get("retrieval_context") or None,
        )
        for t in record.get("turns", [])
    ]
    return ConversationalTestCase(
        turns=turns,
        scenario=record.get("scenario"),
        expected_outcome=record.get("expected_outcome"),
        user_description=record.get("user_description"),
    )


def _turn_cases(record: dict[str, Any]) -> list[LLMTestCase]:
    turns = record.get("turns", [])
    cases: list[LLMTestCase] = []
    for index, turn in enumerate(turns):
        if turn.get("role") != "user":
            continue

        assistant_turn = next(
            (
                candidate
                for candidate in turns[index + 1 :]
                if candidate.get("role") == "assistant"
            ),
            {},
        )
        expected_tools = _tool_calls(turn.get("expected_tools"))
        tools_called = _tool_calls(turn.get("tools_called")) or expected_tools
        retrieval_context = assistant_turn.get("retrieval_context") or []

        cases.append(
            LLMTestCase(
                input=turn.get("content", ""),
                actual_output=assistant_turn.get("content", ""),
                expected_output=assistant_turn.get("content", ""),
                retrieval_context=retrieval_context,
                tools_called=tools_called or None,
                expected_tools=expected_tools or None,
                metadata={
                    "id": record.get("id"),
                    "scenario": record.get("scenario"),
                    "turn_index": len(cases) + 1,
                },
            )
        )
    return cases


_records = _load_records()

_skip_reason: str | None = (
    "Dataset empty — run: uv run python eval/generate_datasets.py"
    if not _records
    else "GOOGLE_API_KEY not set"
    if not os.getenv("GOOGLE_API_KEY")
    else None
)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "record",
    _records or [None],
    ids=[r.get("id", f"MT{i + 1:03d}") for i, r in enumerate(_records)]
    if _records
    else ["skip"],
)
def test_multi_turn(record: dict[str, Any] | None, request: pytest.FixtureRequest):
    if _skip_reason or record is None:
        pytest.skip(_skip_reason or "no test cases")

    assistant_turns = [
        turn for turn in record.get("turns", []) if turn.get("role") == "assistant"
    ]
    request.node.user_properties.append(
        (
            "diagnostic_trace",
            {
                "suite": "multi_turn",
                "category": record.get("scenario"),
                "question": record.get("scenario"),
                "expected": {
                    "answer_checks": [record.get("expected_outcome", "")],
                    "sources": [],
                },
                "actual": {
                    "tool_batches": [],
                    "tool_calls": [],
                    "tool_outputs": [],
                    "retrieval_context": [
                        chunk
                        for turn in assistant_turns
                        for chunk in (turn.get("retrieval_context") or [])
                    ],
                    "final_answer": "\n\n".join(
                        turn.get("content", "") for turn in assistant_turns
                    ),
                    "citations": [],
                },
            },
        )
    )

    for turn_case in _turn_cases(record):
        metrics = [_answer_relevancy]
        if turn_case.retrieval_context:
            metrics.append(_faithfulness)
        if turn_case.expected_tools:
            metrics.append(_tool_correctness)
        assert_test(test_case=turn_case, metrics=metrics, run_async=False)

    conversation_case = _conversation_case(record)
    assert_test(
        test_case=conversation_case,
        metrics=_CONVERSATION_METRICS,
        run_async=False,
    )
