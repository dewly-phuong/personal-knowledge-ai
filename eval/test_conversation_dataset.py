"""
Unified conversation evaluation.

Dataset không phân tách single-turn/multi-turn. Mỗi record trong
eval/datasets/conversation_goldens.json là một cuộc hội thoại dưới 5 turn,
có ground truth output, expected tool calls và retrieval context từ wiki.

Run:
    uv run pytest eval/test_conversation_dataset.py -v

Report:
    uv run python eval/generate_report.py --scores eval/result/scores.jsonl
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest
from dotenv import load_dotenv

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ConversationalGEval,
    FaithfulnessMetric,
    GEval,
    KnowledgeRetentionMetric,
    ToolCorrectnessMetric,
)
from deepeval.test_case import ConversationalTestCase, LLMTestCase, SingleTurnParams
from deepeval.test_case import Turn
from deepeval.test_case.conversational_test_case import MultiTurnParams
from deepeval.test_case.llm_test_case import ToolCall

from eval.judge import GeminiJudge
from eval.metric_capture import assert_test_with_metric_capture
from eval.metric_selection import tool_correctness_enabled

load_dotenv()

DATASET_PATH = Path(__file__).parent / "datasets" / "conversation_goldens.json"

_judge = GeminiJudge()

_answer_relevancy = AnswerRelevancyMetric(threshold=0.5, model=_judge, async_mode=False)
_faithfulness = FaithfulnessMetric(threshold=0.5, model=_judge, async_mode=False)
_tool_correctness = ToolCorrectnessMetric(threshold=0.5, model=_judge)

_domain_faithfulness = GEval(
    name="UnifiedDomainFaithfulness",
    model=_judge,
    async_mode=False,
    evaluation_steps=[
        "Câu trả lời phải bằng tiếng Việt.",
        "Câu trả lời phải bám sát expected_output và retrieval_context, không bịa entity, ngày, số liệu hoặc quan hệ.",
        "Nếu có số liệu, ngày, port, framework, SLA hoặc tên người/service, thông tin đó phải được hỗ trợ bởi retrieval_context.",
        "Câu trả lời nên nêu nguồn hoặc ngữ cảnh tài liệu khi phù hợp.",
    ],
    evaluation_params=[
        SingleTurnParams.INPUT,
        SingleTurnParams.ACTUAL_OUTPUT,
        SingleTurnParams.EXPECTED_OUTPUT,
        SingleTurnParams.RETRIEVAL_CONTEXT,
    ],
    threshold=0.7,
)

_conv_retention = KnowledgeRetentionMetric(
    threshold=0.5, model=_judge, async_mode=False
)
_conv_geval = ConversationalGEval(
    name="UnifiedConversationFaithfulness",
    model=_judge,
    async_mode=False,
    evaluation_params=[
        MultiTurnParams.CONTENT,
        MultiTurnParams.RETRIEVAL_CONTEXT,
    ],
    evaluation_steps=[
        "Trợ lý phải trả lời bằng tiếng Việt trong toàn bộ hội thoại.",
        "Ở lượt sau, trợ lý phải giữ đúng ngữ cảnh từ các lượt trước.",
        "Các entity, quan hệ, số liệu, ngày tháng và SLA trong câu trả lời phải có bằng chứng trong retrieval_context của lượt tương ứng.",
        "Câu trả lời cuối phải đáp ứng đủ nhu cầu của người dùng trong toàn bộ hội thoại.",
    ],
    threshold=0.65,
)


def _load_records() -> list[dict[str, Any]]:
    if not DATASET_PATH.exists():
        return []
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


_records = _load_records()

_skip_reason: str | None = (
    "Dataset empty — missing eval/datasets/conversation_goldens.json"
    if not _records
    else "GOOGLE_API_KEY not set"
    if not os.getenv("GOOGLE_API_KEY")
    else None
)


def _tool_calls(items: list[dict[str, Any]] | None) -> list[ToolCall]:
    return [ToolCall(name=item["name"]) for item in (items or []) if item.get("name")]


def _message_content(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content or "")


def _extract_last_ai(messages: list[Any]) -> str:
    for msg in reversed(messages):
        if type(msg).__name__ == "AIMessage":
            content = _message_content(msg)
            if content:
                return content
    return ""


def _extract_tools(messages: list[Any]) -> list[ToolCall]:
    names: list[str] = []
    for msg in messages:
        if type(msg).__name__ == "AIMessage":
            for call in getattr(msg, "tool_calls", []) or []:
                if isinstance(call, dict) and call.get("name"):
                    names.append(call["name"])
        if type(msg).__name__ == "ToolMessage":
            name = getattr(msg, "name", None)
            if name:
                names.append(name)

    seen = set()
    return [ToolCall(name=n) for n in names if not (n in seen or seen.add(n))]


def _last_user_turn(record: dict[str, Any]) -> dict[str, Any]:
    for turn in reversed(record.get("turns", [])):
        if turn.get("role") == "user":
            return turn
    return {}


def _expected_retrieval(record: dict[str, Any]) -> list[str]:
    contexts = []
    contexts.extend(record.get("retrieval_context") or [])
    for turn in record.get("turns", []):
        contexts.extend(turn.get("retrieval_context") or [])
    return contexts


def _run_agent_conversation(
    record: dict[str, Any],
) -> tuple[list[Turn], list[dict[str, Any]]]:
    from app.agent import create_conversational_agent
    from app.tools.retrieval_context import (
        pop_retrieval_capture,
        start_retrieval_capture,
    )

    agent = create_conversational_agent()
    messages: list[dict[str, str]] = []
    actual_turns: list[Turn] = []
    runs: list[dict[str, Any]] = []

    for turn in record.get("turns", []):
        if turn.get("role") != "user":
            continue

        user_content = turn.get("content", "")
        messages.append({"role": "user", "content": user_content})
        actual_turns.append(Turn(role="user", content=user_content))

        start_retrieval_capture()
        result = agent.invoke({"messages": messages})
        retrieval = pop_retrieval_capture()
        result_messages = result.get("messages", [])
        assistant_content = _extract_last_ai(result_messages)
        tools_called = _extract_tools(result_messages)

        actual_turns.append(
            Turn(
                role="assistant",
                content=assistant_content,
                retrieval_context=retrieval or None,
                tools_called=tools_called or None,
            )
        )
        messages.append({"role": "assistant", "content": assistant_content})
        runs.append(
            {
                "input": user_content,
                "actual_output": assistant_content,
                "retrieval_context": retrieval,
                "tools_called": tools_called,
                "expected_tools": _tool_calls(turn.get("expected_tools")),
            }
        )

    return actual_turns, runs


def _expected_assistant_turns(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [turn for turn in record.get("turns", []) if turn.get("role") == "assistant"]


def _metric_snapshot(metrics: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": _metric_name(metric),
            "score": float(getattr(metric, "score", 0) or 0),
            "threshold": float(getattr(metric, "threshold", 0) or 0),
            "passed": bool(getattr(metric, "success", False)),
            "reason": (getattr(metric, "reason", None) or "").strip(),
        }
        for metric in metrics
    ]


def _metric_name(metric: Any) -> str:
    name = getattr(metric, "name", "")
    if name:
        return name
    class_name = type(metric).__name__.removesuffix("Metric")
    words = []
    for char in class_name:
        if words and char.isupper():
            words.append(" ")
        words.append(char)
    return "".join(words)


def _avg_metric_score(metrics: list[dict[str, Any]]) -> float:
    scores = [float(metric["score"]) for metric in metrics]
    return sum(scores) / len(scores) if scores else 0.0


def _record_conversation_summary(
    request: pytest.FixtureRequest,
    turn_results: list[dict[str, Any]],
    conversation_metrics: list[dict[str, Any]],
) -> None:
    turn_scores = [result["score"] for result in turn_results]
    conversation_score = _avg_metric_score(conversation_metrics)
    request.node.user_properties.append(
        (
            "conversation_eval_summary",
            {
                "turn_average_score": sum(turn_scores) / len(turn_scores)
                if turn_scores
                else None,
                "conversation_score": conversation_score
                if conversation_metrics
                else None,
                "turns_passed": all(result["passed"] for result in turn_results),
                "conversation_passed": all(
                    metric["passed"] for metric in conversation_metrics
                ),
                "turns": turn_results,
                "conversation_metrics": conversation_metrics,
            },
        )
    )


@pytest.mark.parametrize(
    "record",
    _records or [None],
    ids=[r.get("id", f"CV{i + 1:03d}") for i, r in enumerate(_records)]
    if _records
    else ["skip"],
)
def test_conversation_dataset(
    record: dict[str, Any] | None, request: pytest.FixtureRequest
):
    if _skip_reason or record is None:
        pytest.skip(_skip_reason or "no records")

    actual_turns, runs = _run_agent_conversation(record)
    if not actual_turns:
        pytest.skip("record has no user turns")

    expected_retrieval = _expected_retrieval(record)
    expected_assistant_turns = _expected_assistant_turns(record)
    turn_results: list[dict[str, Any]] = []

    for index, run in enumerate(runs):
        expected_turn = (
            expected_assistant_turns[index]
            if index < len(expected_assistant_turns)
            else {}
        )
        turn_retrieval = (
            run["retrieval_context"]
            or expected_turn.get("retrieval_context")
            or expected_retrieval
        )
        expected_tools = run["expected_tools"] or _tool_calls(
            record.get("expected_tools")
        )

        turn_case = LLMTestCase(
            input=run["input"],
            actual_output=run["actual_output"],
            expected_output=expected_turn.get("content", ""),
            context=expected_retrieval,
            retrieval_context=turn_retrieval,
            tools_called=run["tools_called"],
            expected_tools=expected_tools,
            metadata={
                "id": record.get("id"),
                "turn_index": index + 1,
                "scenario": record.get("scenario"),
                "source_files": record.get("source_files", []),
            },
        )

        turn_metrics = [_answer_relevancy, _domain_faithfulness]
        if turn_retrieval:
            turn_metrics.append(_faithfulness)
        if tool_correctness_enabled() and expected_tools:
            turn_metrics.append(_tool_correctness)

        assert_test_with_metric_capture(
            request=request,
            test_case=turn_case,
            metrics=turn_metrics,
            run_async=False,
        )
        metric_results = _metric_snapshot(turn_metrics)
        turn_results.append(
            {
                "turn_index": index + 1,
                "input": run["input"],
                "score": _avg_metric_score(metric_results),
                "passed": all(metric["passed"] for metric in metric_results),
                "metrics": metric_results,
            }
        )

    conv_case = ConversationalTestCase(
        turns=actual_turns,
        scenario=record.get("scenario"),
        expected_outcome=record.get("ground_truth_output"),
        user_description=record.get("user_description"),
        context=expected_retrieval,
        metadata={
            "id": record.get("id"),
            "source_files": record.get("source_files", []),
        },
    )
    conv_metrics = [_conv_geval]
    if len(actual_turns) > 2:
        conv_metrics.insert(0, _conv_retention)
    assert_test_with_metric_capture(
        request=request,
        test_case=conv_case,
        metrics=conv_metrics,
        run_async=False,
    )

    conversation_metrics = _metric_snapshot(conv_metrics)
    _record_conversation_summary(request, turn_results, conversation_metrics)
